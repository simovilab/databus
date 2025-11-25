"""
Tests for the telemetry simulator.
"""

from django.test import TestCase
from django.utils import timezone
from django.contrib.gis.geos import Point

from feed.models import Vehicle, Equipment, Journey, Position, Occupancy, Operator
from gtfs.models import Route, Trip, Stop, StopTime, Shape, Company
from simulator.models import SimulatedVehicle, SimulationLog
from simulator.simulator import VehicleSimulator, SimulationManager


class SimulatorTestCase(TestCase):
    """
    Test cases for the telemetry simulator.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        # Create company
        self.company = Company.objects.create(
            company_id='TEST_COMPANY',
            company_name='Test Company'
        )
        
        # Create operator
        self.operator = Operator.objects.create(
            name='Test Operator'
        )
        
        # Create route
        self.route = Route.objects.create(
            route_id='TEST_ROUTE',
            route_short_name='TR1',
            route_long_name='Test Route',
            route_type=3,  # Bus
            company=self.company
        )
        
        # Create trip
        self.trip = Trip.objects.create(
            trip_id='TEST_TRIP',
            route=self.route,
            direction_id=0,
            shape_id='TEST_SHAPE'
        )
        
        # Create stops
        self.stop1 = Stop.objects.create(
            stop_id='STOP_1',
            stop_name='Stop 1',
            stop_point=Point(-84.0833, 9.9333, srid=4326)
        )
        
        self.stop2 = Stop.objects.create(
            stop_id='STOP_2',
            stop_name='Stop 2',
            stop_point=Point(-84.0843, 9.9343, srid=4326)
        )
        
        # Create stop times
        StopTime.objects.create(
            trip=self.trip,
            stop=self.stop1,
            stop_sequence=1,
            arrival_time='08:00:00',
            departure_time='08:00:00'
        )
        
        StopTime.objects.create(
            trip=self.trip,
            stop=self.stop2,
            stop_sequence=2,
            arrival_time='08:10:00',
            departure_time='08:10:00'
        )
        
        # Create shape points
        Shape.objects.create(
            shape_id='TEST_SHAPE',
            shape_pt_lat=9.9333,
            shape_pt_lon=-84.0833,
            shape_pt_sequence=1,
            shape_dist_traveled=0.0
        )
        
        Shape.objects.create(
            shape_id='TEST_SHAPE',
            shape_pt_lat=9.9343,
            shape_pt_lon=-84.0843,
            shape_pt_sequence=2,
            shape_dist_traveled=1000.0
        )
        
        # Create vehicle
        self.vehicle = Vehicle.objects.create(
            label='TEST-001',
            license_plate='TEST001',
            company=self.company
        )
        
        # Create equipment
        self.equipment = Equipment.objects.create(
            vehicle=self.vehicle,
            provides_position=True,
            provides_occupancy=True
        )
        
        # Create simulated vehicle
        self.simulated_vehicle = SimulatedVehicle.objects.create(
            vehicle=self.vehicle,
            equipment=self.equipment,
            is_active=True,
            speed=10.0
        )
        
        self.simulator = VehicleSimulator(self.simulated_vehicle)
    
    def test_start_journey(self):
        """
        Test starting a journey.
        """
        journey = self.simulator.start_journey(self.trip)
        
        self.assertIsNotNone(journey)
        self.assertEqual(journey.vehicle, self.vehicle)
        self.assertEqual(journey.trip_id, self.trip.trip_id)
        self.assertEqual(journey.journey_status, 'IN_PROGRESS')
        
        # Check that simulated vehicle was updated
        self.simulated_vehicle.refresh_from_db()
        self.assertEqual(self.simulated_vehicle.current_journey, journey)
        self.assertEqual(self.simulated_vehicle.current_stop_index, 0)
        
        # Check that log was created
        log = SimulationLog.objects.filter(
            simulated_vehicle=self.simulated_vehicle,
            event_type='JOURNEY_START'
        ).first()
        self.assertIsNotNone(log)
    
    def test_update_position(self):
        """
        Test updating vehicle position.
        """
        # Start journey first
        journey = self.simulator.start_journey(self.trip)
        
        # Update position
        position = self.simulator.update_position()
        
        self.assertIsNotNone(position)
        self.assertEqual(position.journey, journey)
        self.assertEqual(position.vehicle, self.vehicle)
        self.assertIsNotNone(position.latitude)
        self.assertIsNotNone(position.longitude)
        
        # Check that shape index was incremented
        self.simulated_vehicle.refresh_from_db()
        self.assertEqual(self.simulated_vehicle.current_shape_index, 1)
    
    def test_check_stop_arrival(self):
        """
        Test detecting stop arrival.
        """
        # Start journey and create position near stop
        journey = self.simulator.start_journey(self.trip)
        
        # Create position very close to first stop
        Position.objects.create(
            journey=journey,
            vehicle=self.vehicle,
            timestamp=timezone.now(),
            latitude=9.9333,
            longitude=-84.0833,
            speed=10.0,
            bearing=0.0
        )
        
        # Check for stop arrival
        progression = self.simulator.check_stop_arrival()
        
        self.assertIsNotNone(progression)
        self.assertEqual(progression.stop_id, 'STOP_1')
        
        # Check that occupancy was created
        occupancy = Occupancy.objects.filter(
            journey=journey,
            vehicle=self.vehicle
        ).first()
        self.assertIsNotNone(occupancy)
    
    def test_end_journey(self):
        """
        Test ending a journey.
        """
        journey = self.simulator.start_journey(self.trip)
        
        self.simulator.end_journey()
        
        # Check that journey was marked as completed
        journey.refresh_from_db()
        self.assertEqual(journey.journey_status, 'COMPLETED')
        
        # Check that simulated vehicle was reset
        self.simulated_vehicle.refresh_from_db()
        self.assertIsNone(self.simulated_vehicle.current_journey)
        self.assertEqual(self.simulated_vehicle.current_stop_index, 0)
        
        # Check that log was created
        log = SimulationLog.objects.filter(
            simulated_vehicle=self.simulated_vehicle,
            event_type='JOURNEY_END'
        ).first()
        self.assertIsNotNone(log)
    
    def test_simulation_manager_get_active(self):
        """
        Test getting active simulations.
        """
        active = SimulationManager.get_active_simulations()
        
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first(), self.simulated_vehicle)
        
        # Deactivate and check again
        self.simulated_vehicle.is_active = False
        self.simulated_vehicle.save()
        
        active = SimulationManager.get_active_simulations()
        self.assertEqual(active.count(), 0)
    
    def test_simulation_manager_update_all(self):
        """
        Test updating all active simulations.
        """
        results = SimulationManager.update_all_positions()
        
        # Should have started a journey and created a position
        self.assertGreater(len(results), 0)
        
        # Check that journey was created
        self.simulated_vehicle.refresh_from_db()
        self.assertIsNotNone(self.simulated_vehicle.current_journey)
    
    def test_cleanup_old_logs(self):
        """
        Test cleaning up old simulation logs.
        """
        # Create some old logs
        old_log = SimulationLog.objects.create(
            simulated_vehicle=self.simulated_vehicle,
            event_type='POSITION_UPDATE',
            message='Old log'
        )
        
        # Manually set timestamp to 10 days ago
        old_timestamp = timezone.now() - timezone.timedelta(days=10)
        SimulationLog.objects.filter(id=old_log.id).update(
            timestamp=old_timestamp
        )
        
        # Create a recent log
        recent_log = SimulationLog.objects.create(
            simulated_vehicle=self.simulated_vehicle,
            event_type='POSITION_UPDATE',
            message='Recent log'
        )
        
        # Cleanup logs older than 7 days
        deleted_count = SimulationManager.cleanup_old_logs(days=7)
        
        self.assertEqual(deleted_count, 1)
        
        # Check that old log was deleted
        self.assertFalse(
            SimulationLog.objects.filter(id=old_log.id).exists()
        )
        
        # Check that recent log still exists
        self.assertTrue(
            SimulationLog.objects.filter(id=recent_log.id).exists()
        )
