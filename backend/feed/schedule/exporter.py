"""GTFS Schedule zip exporter.

Reads the Django ORM (the Django-coupled analog of builders.py) and serialises
one Feed instance's rows into a standards-compliant GTFS .zip archive returned
as bytes.  Also exposes ``publish_gtfs_zip`` to write the archive to disk
atomically; this shared helper is used by both the Celery task and the
management command.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from django.db import models as db_models

from feed.models import (
    Agency,
    Calendar,
    CalendarDate,
    FareAttribute,
    FareRule,
    FeedInfo,
    Route,
    Shape,
    Stop,
    StopTime,
    Trip,
)

if TYPE_CHECKING:
    from feed.models import Feed


# ---------------------------------------------------------------------------
# Field introspection helpers
# ---------------------------------------------------------------------------

_EXCLUDE_NAMES: frozenset[str] = frozenset(
    {"id", "feed", "geoshape", "stop_point", "stop_heading", "holiday_name"}
)


def _gtfs_fields(model: type[db_models.Model]) -> list[tuple[str, db_models.Field]]:
    """Return ``(column_name, field)`` pairs for GTFS output in declaration order.

    Excluded: the internal auto-pk, the ``feed`` FK, any field whose name
    starts with ``linked_``, and the app-specific augmentation fields listed
    in ``_EXCLUDE_NAMES``.  All remaining fields after exclusion are concrete
    non-FK fields, so ``field.attname == field.name`` and equals the GTFS
    column name.
    """
    result: list[tuple[str, db_models.Field]] = []
    for field in model._meta.local_fields:
        if field.name in _EXCLUDE_NAMES or field.name.startswith("linked_"):
            continue
        result.append((field.attname, field))
    return result


def _format_value(field: db_models.Field, value: object) -> str:
    """Format a model field value as a GTFS CSV cell string."""
    if value is None:
        return ""
    # DateField (but NOT DateTimeField which subclasses DateField)
    if isinstance(field, db_models.DateField) and not isinstance(
        field, db_models.DateTimeField
    ):
        return value.strftime("%Y%m%d")  # type: ignore[union-attr]
    if isinstance(field, db_models.TimeField):
        return value.strftime("%H:%M:%S")  # type: ignore[union-attr]
    if isinstance(field, db_models.BooleanField):
        return "1" if value else "0"
    return str(value)


# ---------------------------------------------------------------------------
# Zip assembly
# ---------------------------------------------------------------------------


def _write_txt(
    zf: zipfile.ZipFile,
    filename: str,
    model: type[db_models.Model],
    queryset,
) -> None:
    """Write one GTFS ``.txt`` file into *zf*.

    The file is omitted from the archive if the queryset has zero rows.
    """
    fields = _gtfs_fields(model)
    columns = [col for col, _ in fields]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)

    count = 0
    for obj in queryset.iterator():
        row = [_format_value(fld, getattr(obj, col)) for col, fld in fields]
        writer.writerow(row)
        count += 1

    if count > 0:
        zf.writestr(filename, buf.getvalue())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_gtfs_zip(feed: "Feed") -> bytes:
    """Serialise one ``Feed`` instance into a GTFS zip and return the raw bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_txt(zf, "agency.txt", Agency, Agency.objects.filter(feed=feed))
        _write_txt(zf, "stops.txt", Stop, Stop.objects.filter(feed=feed))
        _write_txt(zf, "routes.txt", Route, Route.objects.filter(feed=feed))
        _write_txt(zf, "calendar.txt", Calendar, Calendar.objects.filter(feed=feed))
        _write_txt(
            zf,
            "calendar_dates.txt",
            CalendarDate,
            CalendarDate.objects.filter(feed=feed),
        )
        _write_txt(
            zf,
            "shapes.txt",
            Shape,
            Shape.objects.filter(feed=feed).order_by("shape_id", "shape_pt_sequence"),
        )
        _write_txt(zf, "trips.txt", Trip, Trip.objects.filter(feed=feed))
        _write_txt(
            zf,
            "stop_times.txt",
            StopTime,
            StopTime.objects.filter(feed=feed).order_by("trip_id", "stop_sequence"),
        )
        _write_txt(
            zf,
            "fare_attributes.txt",
            FareAttribute,
            FareAttribute.objects.filter(feed=feed),
        )
        _write_txt(
            zf,
            "fare_rules.txt",
            FareRule,
            FareRule.objects.filter(feed=feed),
        )
        _write_txt(
            zf,
            "feed_info.txt",
            FeedInfo,
            FeedInfo.objects.filter(feed=feed),
        )
    return buf.getvalue()


def publish_gtfs_zip(feed: "Feed", output_dir: Path | None = None) -> Path:
    """Build the GTFS zip and write it atomically to ``<output_dir>/gtfs.zip``.

    If *output_dir* is ``None``, defaults to ``settings.BASE_DIR / "feed" / "files"``.
    Uses a ``.tmp`` staging file and ``Path.replace`` (atomic rename) to avoid
    partially-written files being served.  Returns the final ``Path``.
    """
    from django.conf import settings

    if output_dir is None:
        output_dir = settings.BASE_DIR / "feed" / "files"

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "gtfs.zip"
    tmp = output_dir / "gtfs.zip.tmp"

    tmp.write_bytes(build_gtfs_zip(feed))
    tmp.replace(dest)
    return dest
