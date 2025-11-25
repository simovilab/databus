"""
Telemetry and tracking data simulator for testing the Databus system.

This module simulates vehicle movement along GTFS routes and sends
telemetry data to the realtime API endpoints.
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import math

from django.utils import timezone
from django.contrib.gis.geos import Point
from django.db import transaction

from gtfs.models import Trip, StopTime, Shape
from feed.models import Vehicle, Equipment, Journey, Position, Progression, Occupancy
from .models import SimulatedVehicle, SimulationLog

logger = logging.getLogger(__name__)


class VehicleSimulator:
    """
    Simulates a single vehicle moving along a route.
    """
    
    def __init__(self, simulated_vehicle: SimulatedVehicle):
        self.simulated_vehicle = simulated_vehicle
        self.vehicle = simulated_vehicle.vehicle
        
    def start_journey(self, trip: Trip) -> Optional[Journey]:
        """
        Start a new journey for this vehicle.
        """
        try:
            # Get operator (use first available or create dummy)
            from feed.models import Operator
            operator = Operator.objects.first()
            
            if not operator:
                logger.warning("No operator found, journey requires operator")
                return None
            
            # Create journey
            journey = Journey.objects.create(
                vehicle=self.vehicle,
                equipment=self.simulated_vehicle.equipment,
                operator=operator,
                route_id=trip.route_id,
                trip_id=trip.trip_id,
                direction_id=trip.direction_id,
                shape_id=trip.shape_id,
                start_date=timezone.now().date(),
                start_time=timezone.now().time(),
                schedule_relationship='SCHEDULED',
                journey_status='IN_PROGRESS'
            )
            
            # Update simulated vehicle
            self.simulated_vehicle.current_journey = journey
            self.simulated_vehicle.current_stop_index = 0
            self.simulated_vehicle.current_shape_index = 0
            self.simulated_vehicle.save()
            
            # Log event
            SimulationLog.objects.create(
                simulated_vehicle=self.simulated_vehicle,
                event_type='JOURNEY_START',
                message=f"Started journey {trip.trip_id}",
                data={'trip_id': trip.trip_id, 'journey_id': journey.id}
            )
            
            logger.info(f"Started journey {journey.id} for vehicle {self.vehicle.license_plate}")
            return journey
            
        except Exception as e:
            logger.error(f"Error starting journey: {e}")
            SimulationLog.objects.create(
                simulated_vehicle=self.simulated_vehicle,
                event_type='ERROR',
                message=f"Failed to start journey: {str(e)}"
            )
            return None
    
    def update_position(self) -> Optional[Position]:
        """
        Update vehicle position based on current journey progress.
        """
        if not self.simulated_vehicle.current_journey:
            return None
            
        try:
            journey = self.simulated_vehicle.current_journey
            
            # Get shape points for this journey
            shape_points = Shape.objects.filter(
                shape_id=journey.shape_id
            ).order_by('shape_pt_sequence')
            
            if not shape_points.exists():
                logger.warning(f"No shape points found for shape_id {journey.shape_id}")
                return None
            
            # Get current shape point
            shape_index = self.simulated_vehicle.current_shape_index
            if shape_index >= shape_points.count():
                # Journey complete
                self.end_journey()
                return None
            
            current_point = shape_points[shape_index]
            
            # Calculate bearing to next point if available
            bearing = 0.0
            if shape_index < shape_points.count() - 1:
                next_point = shape_points[shape_index + 1]
                bearing = self._calculate_bearing(
                    current_point.shape_pt_lat,
                    current_point.shape_pt_lon,
                    next_point.shape_pt_lat,
                    next_point.shape_pt_lon
                )
            
            # Create position update
            position = Position.objects.create(
                journey=journey,
                vehicle=self.vehicle,
                timestamp=timezone.now(),
                latitude=float(current_point.shape_pt_lat),
                longitude=float(current_point.shape_pt_lon),
                speed=self.simulated_vehicle.speed,
                bearing=bearing,
                odometer=float(current_point.shape_dist_traveled) if current_point.shape_dist_traveled else 0.0
            )
            
            # Move to next shape point
            self.simulated_vehicle.current_shape_index += 1
            self.simulated_vehicle.save()
            
            # Log event
            SimulationLog.objects.create(
                simulated_vehicle=self.simulated_vehicle,
                event_type='POSITION_UPDATE',
                message=f"Position updated",
                data={
                    'lat': position.latitude,
                    'lon': position.longitude,
                    'speed': position.speed
                }
            )
            
            return position
            
        except Exception as e:
            logger.error(f"Error updating position: {e}")
            SimulationLog.objects.create(
                simulated_vehicle=self.simulated_vehicle,
                event_type='ERROR',
                message=f"Failed to update position: {str(e)}"
            )
            return None
    
    def check_stop_arrival(self) -> Optional[Progression]:
        """
        Check if vehicle has arrived at a stop and update progression.
        """
        if not self.simulated_vehicle.current_journey:
            return None
            
        try:
            journey = self.simulated_vehicle.current_journey
            
            # Get stop times for this trip
            stop_times = StopTime.objects.filter(
                trip__trip_id=journey.trip_id
            ).order_by('stop_sequence')
            
            if not stop_times.exists():
                return None
            
            stop_index = self.simulated_vehicle.current_stop_index
            if stop_index >= stop_times.count():
                return None
            
            current_stop = stop_times[stop_index]
            
            # Get current position
            latest_position = Position.objects.filter(
                journey=journey
            ).order_by('-timestamp').first()
            
            if not latest_position:
                return None
            
            # Check if we're close to the stop (within 50 meters)
            stop_location = current_stop.stop.stop_point
            vehicle_location = Point(latest_position.longitude, latest_position.latitude, srid=4326)
            
            distance = stop_location.distance(vehicle_location) * 111139  # Convert to meters (approximate)
            
            if distance < 50:  # Within 50 meters
                # Create progression update
                progression = Progression.objects.create(
                    journey=journey,
                    vehicle=self.vehicle,
                    timestamp=timezone.now(),
                    current_stop_sequence=current_stop.stop_sequence,
                    stop_id=current_stop.stop_id,
                    current_status='STOPPED_AT',
                    congestion_level=random.choice(['RUNNING_SMOOTHLY', 'STOP_AND_GO', 'CONGESTION'])
                )
                
                # Update occupancy
                self.update_occupancy()
                
                # Move to next stop
                self.simulated_vehicle.current_stop_index += 1
                self.simulated_vehicle.save()
                
                # Log event
                SimulationLog.objects.create(
                    simulated_vehicle=self.simulated_vehicle,
                    event_type='STOP_ARRIVAL',
                    message=f"Arrived at stop {current_stop.stop_id}",
                    data={
                        'stop_id': current_stop.stop_id,
                        'stop_sequence': current_stop.stop_sequence
                    }
                )
                
                return progression
                
        except Exception as e:
            logger.error(f"Error checking stop arrival: {e}")
            return None
    
    def update_occupancy(self) -> Optional[Occupancy]:
        """
        Update vehicle occupancy at current stop.
        """
        if not self.simulated_vehicle.current_journey:
            return None
            
        try:
            journey = self.simulated_vehicle.current_journey
            
            # Generate random but realistic occupancy
            occupancy_percentage = random.randint(20, 95)
            occupancy_count = random.randint(5, 40)
            
            # Determine occupancy status based on percentage
            if occupancy_percentage < 30:
                status = 'MANY_SEATS_AVAILABLE'
            elif occupancy_percentage < 60:
                status = 'FEW_SEATS_AVAILABLE'
            elif occupancy_percentage < 80:
                status = 'STANDING_ROOM_ONLY'
            elif occupancy_percentage < 95:
                status = 'CRUSHED_STANDING_ROOM_ONLY'
            else:
                status = 'FULL'
            
            occupancy = Occupancy.objects.create(
                journey=journey,
                vehicle=self.vehicle,
                timestamp=timezone.now(),
                occupancy_status=status,
                occupancy_percentage=occupancy_percentage,
                occupancy_count=occupancy_count
            )
            
            # Log event
            SimulationLog.objects.create(
                simulated_vehicle=self.simulated_vehicle,
                event_type='OCCUPANCY_UPDATE',
                message=f"Occupancy updated: {status}",
                data={
                    'percentage': occupancy_percentage,
                    'count': occupancy_count
                }
            )
            
            return occupancy
            
        except Exception as e:
            logger.error(f"Error updating occupancy: {e}")
            return None
    
    def end_journey(self):
        """
        End the current journey.
        """
        if not self.simulated_vehicle.current_journey:
            return
            
        try:
            journey = self.simulated_vehicle.current_journey
            journey.journey_status = 'COMPLETED'
            journey.save()
            
            # Log event
            SimulationLog.objects.create(
                simulated_vehicle=self.simulated_vehicle,
                event_type='JOURNEY_END',
                message=f"Journey {journey.id} completed"
            )
            
            # Reset simulated vehicle
            self.simulated_vehicle.current_journey = None
            self.simulated_vehicle.current_stop_index = 0
            self.simulated_vehicle.current_shape_index = 0
            self.simulated_vehicle.save()
            
            logger.info(f"Ended journey {journey.id} for vehicle {self.vehicle.license_plate}")
            
        except Exception as e:
            logger.error(f"Error ending journey: {e}")
    
    @staticmethod
    def _calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate bearing between two geographic points.
        """
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)
        
        x = math.sin(delta_lon) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
        
        bearing = math.atan2(x, y)
        bearing = math.degrees(bearing)
        bearing = (bearing + 360) % 360
        
        return bearing


class SimulationManager:
    """
    Manages all active vehicle simulations.
    """
    
    @staticmethod
    def get_active_simulations():
        """
        Get all active simulated vehicles.
        """
        return SimulatedVehicle.objects.filter(is_active=True)
    
    @staticmethod
    def update_all_positions():
        """
        Update positions for all active simulated vehicles.
        """
        active_sims = SimulationManager.get_active_simulations()
        results = []
        
        for sim in active_sims:
            simulator = VehicleSimulator(sim)
            
            # If no current journey, try to start one
            if not sim.current_journey:
                # Get a random trip for this vehicle's routes
                trip = Trip.objects.filter(
                    route__company=sim.vehicle.company
                ).order_by('?').first()
                
                if trip:
                    simulator.start_journey(trip)
            
            # Update position
            position = simulator.update_position()
            if position:
                results.append({
                    'vehicle': sim.vehicle.license_plate,
                    'position': position.id
                })
            
            # Check for stop arrivals
            simulator.check_stop_arrival()
        
        return results
    
    @staticmethod
    def cleanup_old_logs(days: int = 7):
        """
        Remove simulation logs older than specified days.
        """
        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = SimulationLog.objects.filter(
            timestamp__lt=cutoff
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old simulation logs")
        return deleted_count
