"""Management command: import each active publisher's GTFS Schedule when it has none yet.

Complements the hourly `schedule_engine.tasks.fetch_schedule` beat task. That
task keeps an already-imported schedule in sync; this command covers the cold
start, where a freshly migrated database has no `Feed` at all and would
otherwise serve empty GTFS-RT feeds until the next beat tick fires.

Runs the import synchronously and in-process, so it works during container
startup before any Celery worker or broker is reachable.
"""

from typing import Any

from django.core.management.base import BaseCommand

from feed.models import Feed, FeedPublisher
from feed.schedule.importer import import_schedule_if_changed


class Command(BaseCommand):
    """Import the GTFS Schedule for every active publisher that has no current Feed."""

    help = (
        "Import the GTFS Schedule for every active FeedPublisher that has no "
        "current Feed. Publishers that already have one are left untouched; "
        "the hourly fetch_schedule task keeps those up to date."
    )

    def add_arguments(self, parser: Any) -> None:
        """Register the --force flag, which re-checks publishers that already have a feed."""
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Also check publishers that already have a current Feed, "
                "importing when the upstream ETag has changed (what the "
                "hourly task does)."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Import schedules for publishers missing a current Feed, reporting what happened."""
        force: bool = options["force"]

        publishers = list(FeedPublisher.objects.filter(is_active=True))
        if not publishers:
            self.stdout.write(
                self.style.WARNING(
                    "No active FeedPublisher rows found; nothing to bootstrap."
                )
            )
            return

        imported: list[str] = []
        skipped: list[str] = []
        failed: list[str] = []

        for publisher in publishers:
            has_feed = Feed.objects.filter(
                feed_publisher=publisher, is_current=True
            ).exists()
            if has_feed and not force:
                skipped.append(publisher.code)
                self.stdout.write(
                    f"{publisher.code}: already has a current Feed; skipping."
                )
                continue

            self.stdout.write(f"{publisher.code}: importing {publisher.schedule_url} ...")
            # import_schedule_if_changed swallows its own network/parse errors
            # and returns False; the broad except is for anything it doesn't
            # catch, so one bad publisher can't abort the whole bootstrap.
            try:
                changed = import_schedule_if_changed(publisher)
            except Exception as exc:  # noqa: BLE001 - reported, not silenced
                failed.append(publisher.code)
                self.stderr.write(
                    self.style.ERROR(f"{publisher.code}: import raised {exc!r}")
                )
                continue

            if changed:
                imported.append(publisher.code)
                self.stdout.write(self.style.SUCCESS(f"{publisher.code}: imported."))
            elif has_feed:
                skipped.append(publisher.code)
                self.stdout.write(f"{publisher.code}: already up to date.")
            else:
                # No feed before, and none imported now -- the importer logged
                # the reason (unreachable host, bad zip, missing URL).
                failed.append(publisher.code)
                self.stderr.write(
                    self.style.ERROR(
                        f"{publisher.code}: no schedule imported; see the log above."
                    )
                )

        summary = (
            f"bootstrap_schedule: imported={imported} "
            f"skipped={skipped} failed={failed}"
        )
        style = self.style.WARNING if failed else self.style.SUCCESS
        self.stdout.write(style(summary))
