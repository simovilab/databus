"""Management command: export the current GTFS feed to feed/files/gtfs.zip."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from feed.models import Feed
from feed.schedule.exporter import publish_gtfs_zip


class Command(BaseCommand):
    """Export the current GTFS feed (is_current=True) to feed/files/gtfs.zip."""

    help = "Export the current GTFS feed (is_current=True) to feed/files/gtfs.zip"

    def handle(self, *args: Any, **options: Any) -> None:
        """Locate the current Feed and publish its GTFS Schedule zip to disk."""
        feed = Feed.objects.filter(is_current=True).first()
        if feed is None:
            raise CommandError(
                "No Feed with is_current=True found. "
                "Load the fixture first: manage.py loaddata gtfs.json"
            )

        dest = publish_gtfs_zip(feed)
        self.stdout.write(
            self.style.SUCCESS(
                f"GTFS Schedule zip exported: {dest} ({dest.stat().st_size} bytes)"
            )
        )
