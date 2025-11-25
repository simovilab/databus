"""
Django management command to start vehicle simulation.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from feed.models import Vehicle, Equipment
from simulator.models import SimulatedVehicle


class Command(BaseCommand):
    help = 'Start simulation for a vehicle'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vehicle',
            type=str,
            help='Vehicle ID or license plate'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Start simulation for all vehicles'
        )
        parser.add_argument(
            '--speed',
            type=float,
            default=10.0,
            help='Simulation speed in m/s (default: 10.0)'
        )

    def handle(self, *args, **options):
        if options['all']:
            vehicles = Vehicle.objects.all()
            created_count = 0
            
            for vehicle in vehicles:
                equipment = Equipment.objects.filter(
                    vehicle=vehicle,
                    provides_position=True
                ).first()
                
                sim, created = SimulatedVehicle.objects.get_or_create(
                    vehicle=vehicle,
                    defaults={
                        'equipment': equipment,
                        'is_active': True,
                        'speed': options['speed']
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Started simulation for {vehicle.license_plate}"
                        )
                    )
                else:
                    sim.is_active = True
                    sim.speed = options['speed']
                    sim.save()
                    self.stdout.write(
                        self.style.WARNING(
                            f"Updated simulation for {vehicle.license_plate}"
                        )
                    )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Started simulation for {created_count} vehicles"
                )
            )
        
        elif options['vehicle']:
            try:
                vehicle = Vehicle.objects.get(
                    models.Q(id=options['vehicle']) | 
                    models.Q(license_plate=options['vehicle'])
                )
            except Vehicle.DoesNotExist:
                raise CommandError(f"Vehicle '{options['vehicle']}' not found")
            
            equipment = Equipment.objects.filter(
                vehicle=vehicle,
                provides_position=True
            ).first()
            
            sim, created = SimulatedVehicle.objects.get_or_create(
                vehicle=vehicle,
                defaults={
                    'equipment': equipment,
                    'is_active': True,
                    'speed': options['speed']
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Started simulation for {vehicle.license_plate}"
                    )
                )
            else:
                sim.is_active = True
                sim.speed = options['speed']
                sim.save()
                self.stdout.write(
                    self.style.WARNING(
                        f"Updated simulation for {vehicle.license_plate}"
                    )
                )
        else:
            raise CommandError("Specify --vehicle or --all")
