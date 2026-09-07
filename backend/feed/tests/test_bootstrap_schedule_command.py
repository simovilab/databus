"""Tests for the `bootstrap_schedule` management command.

The command's whole job is deciding *which* publishers to import for, so
`import_schedule_if_changed` is patched out throughout — the import itself is
covered by `test_schedule_importer.py`.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from feed.models import Feed, FeedPublisher, TransitSystem

IMPORTER = "feed.management.commands.bootstrap_schedule.import_schedule_if_changed"


class TestBootstrapScheduleCommand(TestCase):
    """Verify which publishers the command imports for, and what it reports."""

    def _publisher(self, code: str = "SIMOVI", **kwargs: object) -> FeedPublisher:
        """Create an active FeedPublisher with a usable schedule_url."""
        system, _ = TransitSystem.objects.get_or_create(
            code="bUCR", defaults={"name": "bUCR", "is_active": True}
        )
        defaults: dict = {
            "transit_system": system,
            "code": code,
            "name": code,
            "schedule_url": "https://feeds.example.org/gtfs.zip",
            "timezone": "America/Costa_Rica",
            "is_active": True,
        }
        defaults.update(kwargs)
        return FeedPublisher.objects.create(**defaults)

    def _run(self, *args: str) -> str:
        """Call the command, returning its combined stdout+stderr."""
        out, err = StringIO(), StringIO()
        call_command("bootstrap_schedule", *args, stdout=out, stderr=err)
        return out.getvalue() + err.getvalue()

    def test_imports_when_publisher_has_no_feed(self) -> None:
        """A publisher with no current Feed triggers an import."""
        publisher = self._publisher()
        with patch(IMPORTER, return_value=True) as mock_import:
            output = self._run()
        mock_import.assert_called_once_with(publisher)
        self.assertIn("imported=['SIMOVI']", output)

    def test_skips_publisher_that_already_has_a_feed(self) -> None:
        """A publisher with a current Feed is skipped without any HTTP work."""
        publisher = self._publisher()
        Feed.objects.create(feed_id="f1", feed_publisher=publisher, is_current=True)
        with patch(IMPORTER) as mock_import:
            output = self._run()
        mock_import.assert_not_called()
        self.assertIn("skipped=['SIMOVI']", output)

    def test_force_rechecks_publisher_that_already_has_a_feed(self) -> None:
        """--force checks a publisher that already has a Feed, as the hourly task does."""
        publisher = self._publisher()
        Feed.objects.create(feed_id="f1", feed_publisher=publisher, is_current=True)
        with patch(IMPORTER, return_value=False) as mock_import:
            output = self._run("--force")
        mock_import.assert_called_once_with(publisher)
        self.assertIn("skipped=['SIMOVI']", output)

    def test_inactive_publisher_is_never_touched(self) -> None:
        """Publishers with is_active=False are outside the command's scope."""
        self._publisher(is_active=False)
        with patch(IMPORTER) as mock_import:
            output = self._run()
        mock_import.assert_not_called()
        self.assertIn("No active FeedPublisher", output)

    def test_failed_import_is_reported_not_raised(self) -> None:
        """A publisher whose import yields no feed is reported as failed."""
        self._publisher()
        with patch(IMPORTER, return_value=False):
            output = self._run()
        self.assertIn("failed=['SIMOVI']", output)

    def test_one_raising_publisher_does_not_abort_the_others(self) -> None:
        """An exception on one publisher is caught so the rest still import."""
        self._publisher(code="AAA")
        self._publisher(code="BBB")

        def _side_effect(publisher: FeedPublisher) -> bool:
            if publisher.code == "AAA":
                raise RuntimeError("upstream exploded")
            return True

        with patch(IMPORTER, side_effect=_side_effect) as mock_import:
            output = self._run()
        self.assertEqual(mock_import.call_count, 2)
        self.assertIn("imported=['BBB']", output)
        self.assertIn("failed=['AAA']", output)
