"""
Django management command to stop vehicle simulation.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from feed.models import Vehicle
from simulator.models import SimulatedVehicle


class Command(BaseCommand):
    help = 'Stop simulation for a vehicle'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vehicle',
            type=str,
            help='Vehicle ID or license plate'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Stop simulation for all vehicles'
        )

    def handle(self, *args, **options):
        if options['all']:
            count = SimulatedVehicle.objects.filter(is_active=True).update(
                is_active=False
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Stopped simulation for {count} vehicles"
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
            
            try:
                sim = SimulatedVehicle.objects.get(vehicle=vehicle)
                sim.is_active = False
                sim.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Stopped simulation for {vehicle.license_plate}"
                    )
                )
            except SimulatedVehicle.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"No simulation found for {vehicle.license_plate}"
                    )
                )
        else:
            raise CommandError("Specify --vehicle or --all")
