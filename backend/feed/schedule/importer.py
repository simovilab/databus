"""GTFS Schedule zip importer.

Ported from infobús's ``save_schedule_to_database``, adapted for databús's
``FeedPublisher``/``Feed`` schema. HEAD-checks a provider's upstream
``schedule_url`` ETag; if it differs from the current ``Feed``'s, downloads
and bulk-imports the new GTFS zip table-by-table, flips ``is_current``, and
returns ``True``.

Core ``linked_*`` FKs (e.g. ``Trip.linked_route``) are intentionally left
``NULL`` here: they're normally resolved in each model's custom ``save()``,
which ``bulk_create`` bypasses for performance, and nothing downstream reads
them (the exporter re-derives GTFS columns from natural keys and already
excludes ``linked_*``). ``Stop.stop_point`` is the one exception: it's built
inline via ``Point(lon, lat)`` because it's needed for geo queries and
``Stop.save()`` is bypassed too.
"""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import date, datetime, timezone

import pandas as pd
import requests
from django.contrib.gis.geos import Point
from django.db import models as db_models
from django.db import transaction

from feed.models import (
    Agency,
    Calendar,
    CalendarDate,
    Feed,
    FeedInfo,
    FeedPublisher,
    Route,
    Shape,
    Stop,
    StopTime,
    Trip,
)

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30  # seconds

# Mirrors feed.schedule.exporter._EXCLUDE_NAMES so importer/exporter agree on
# which columns are GTFS data vs. internal/app-specific augmentation fields.
_EXCLUDE_FIELD_NAMES = frozenset(
    {"id", "feed", "geoshape", "stop_point", "stop_heading", "holiday_name"}
)

# Columns holding GTFS "YYYYMMDD" dates, which must be converted to `date`
# objects before construction (Django's DateField.to_python expects ISO
# "YYYY-MM-DD", not GTFS's compact format).
_DATE_FIELDS: dict[type[db_models.Model], frozenset[str]] = {
    Calendar: frozenset({"start_date", "end_date"}),
    CalendarDate: frozenset({"date"}),
    FeedInfo: frozenset({"feed_start_date", "feed_end_date"}),
}

# Import order matters: GTFS tables have no cross-table FK constraints in
# this schema (linked_* are left NULL), so order here just mirrors the GTFS
# reference table listing for readability/parity with infobús and the
# exporter. Fare tables are intentionally out of scope (see plan).
_TABLES: list[tuple[str, type[db_models.Model]]] = [
    ("agency", Agency),
    ("stops", Stop),
    ("shapes", Shape),
    ("calendar", Calendar),
    ("calendar_dates", CalendarDate),
    ("routes", Route),
    ("trips", Trip),
    ("stop_times", StopTime),
    ("feed_info", FeedInfo),
]


def normalize_gtfs_value(value: object) -> str | None:
    """Normalize a raw CSV cell: blank/whitespace-only/NaN -> None, else stripped string."""
    if value is None:
        return None
    # pandas keeps genuinely-missing cells as float NaN even under
    # dtype=str (a str column can't hold NaN, so it stays a float);
    # str(nan) == "nan", which would otherwise pass through as a bogus value.
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def gtfs_date(value: object) -> date | None:
    """Parse a GTFS ``YYYYMMDD`` string into a ``date``. None-safe."""
    text = normalize_gtfs_value(value)
    if text is None:
        return None
    return datetime.strptime(text, "%Y%m%d").date()


def _importable_fields(model: type[db_models.Model]) -> list[db_models.Field]:
    """Return the concrete, importable fields for *model* (excludes FKs/augmentation fields)."""
    return [
        field
        for field in model._meta.local_fields
        if field.name not in _EXCLUDE_FIELD_NAMES
        and not field.name.startswith("linked_")
    ]


def _model_fields(model: type[db_models.Model]) -> list[str]:
    """Return the concrete, importable column names for *model*."""
    return [field.attname for field in _importable_fields(model)]


def _empty_value_for(field: db_models.Field) -> object:
    """Return a safe non-NULL substitute for a blank cell on a non-nullable *field*.

    Priority: the field's own Django-level default (if any) > 0 for numeric
    fields > "" for text fields > None as a last resort (which will surface
    as a NOT NULL violation, but only for fields we truly can't infer a safe
    empty value for -- better a loud DB error than a silently wrong guess).
    """
    if field.has_default():
        return field.get_default()
    if isinstance(
        field, (db_models.IntegerField, db_models.FloatField, db_models.DecimalField)
    ):
        return 0
    if isinstance(field, (db_models.CharField, db_models.TextField)):
        return ""
    return None


def _coerce_row(
    model: type[db_models.Model], row: dict[str, object]
) -> dict[str, object]:
    """Normalize one CSV row's raw string values into model constructor kwargs.

    Iterates *model*'s full importable field set -- not just the columns
    present in *row* -- because a lean GTFS feed can omit an entire column
    (e.g. a stop_times.txt with no pickup_type/drop_off_type columns at
    all). A column that's present-but-blank and a column that's absent
    entirely must be treated the same way: if the resulting value is None
    and the Django field is non-nullable, substitute a safe empty value
    (see `_empty_value_for`) instead of leaving/passing None.
    """
    date_fields = _DATE_FIELDS.get(model, frozenset())

    kwargs: dict[str, object] = {}
    for field in _importable_fields(model):
        column = field.attname
        value: object
        if column in row:
            raw_value = row[column]
            value = (
                gtfs_date(raw_value)
                if column in date_fields
                else normalize_gtfs_value(raw_value)
            )
        else:
            value = None

        if value is None and not field.null:
            value = _empty_value_for(field)

        kwargs[column] = value
    return kwargs


def _build_stop_point(row: dict[str, object]) -> Point | None:
    """Build a ``Point(lon, lat)`` from a stops.txt row, or None if lat/lon is missing."""
    lat = normalize_gtfs_value(row.get("stop_lat"))
    lon = normalize_gtfs_value(row.get("stop_lon"))
    if lat is None or lon is None:
        return None
    try:
        return Point(float(lon), float(lat))
    except (TypeError, ValueError) as exc:
        logger.warning(
            "Skipping stop_point for row with bad lat/lon (%s, %s): %s", lat, lon, exc
        )
        return None


def _import_table(
    table_name: str, model: type[db_models.Model], zf: zipfile.ZipFile, feed: Feed
) -> int:
    """Import one GTFS ``.txt`` file from *zf* into *model*, tagged with *feed*."""
    filename = f"{table_name}.txt"
    if filename not in zf.namelist():
        return 0

    fields = _model_fields(model)
    table = pd.read_csv(
        zf.open(filename), dtype=str, keep_default_na=False, na_values=""
    )
    columns = [c for c in fields if c in table.columns]
    table = table[columns]

    instances: list[db_models.Model] = []
    for raw_row in table.to_dict(orient="records"):
        try:
            kwargs = _coerce_row(model, raw_row)
            kwargs["feed"] = feed
            if model is Stop:
                kwargs["stop_point"] = _build_stop_point(raw_row)
            instances.append(model(**kwargs))
        except (ValueError, TypeError) as exc:
            # E.g. a GTFS time hour >= 24 (TimeField can't hold it), or a
            # malformed date/decimal. Logged and skipped rather than
            # aborting the whole table/import for one bad row.
            logger.warning("Skipping malformed %s row %r: %s", table_name, raw_row, exc)

    # `model` is a `type[db_models.Model]` parameter (any of the concrete
    # feed.models classes at call sites below); django-stubs can't resolve
    # `.objects` on the generic base-class type here even though every
    # concrete subclass has it via Django's default manager.
    model.objects.bulk_create(instances, batch_size=2000)  # type: ignore[attr-defined]
    return len(instances)


def _resolve_new_etag(resp: requests.Response) -> str | None:
    """Prefer the ETag header; fall back to Last-Modified. None means 'always import'."""
    etag = resp.headers.get("ETag")
    if etag:
        return etag
    return resp.headers.get("Last-Modified")


def _parse_last_modified(resp: requests.Response) -> datetime:
    """Parse the Last-Modified header into a UTC datetime, defaulting to now() if absent/invalid."""
    raw = resp.headers.get("Last-Modified")
    if not raw:
        return datetime.now(timezone.utc)
    try:
        return datetime.strptime(raw, "%a, %d %b %Y %H:%M:%S %Z").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        logger.warning("Unparseable Last-Modified header %r; using now()", raw)
        return datetime.now(timezone.utc)


def import_schedule_if_changed(provider: FeedPublisher) -> bool:
    """Import *provider*'s GTFS Schedule zip when its upstream ETag changed.

    Returns True if a new Feed was imported, False if unchanged or on error.
    """
    if not provider.schedule_url:
        logger.warning("FeedPublisher %s has no schedule_url; skipping", provider.code)
        return False

    current_feed = (
        Feed.objects.filter(feed_publisher=provider, is_current=True)
        .order_by("-retrieved_at")
        .first()
    )
    current_tag = current_feed.http_etag if current_feed else None

    try:
        head_resp = requests.head(provider.schedule_url, timeout=_REQUEST_TIMEOUT)
        head_resp.raise_for_status()
    except requests.RequestException:
        logger.exception("HEAD request failed for provider %s", provider.code)
        return False

    new_tag = _resolve_new_etag(head_resp)
    if new_tag is not None and new_tag == current_tag:
        logger.info("Provider %s schedule up to date (etag=%s)", provider.code, new_tag)
        return False

    try:
        get_resp = requests.get(provider.schedule_url, timeout=_REQUEST_TIMEOUT)
        get_resp.raise_for_status()
        schedule_zip = zipfile.ZipFile(io.BytesIO(get_resp.content))
    except requests.RequestException, zipfile.BadZipFile:
        logger.exception(
            "Failed to download/parse schedule zip for provider %s", provider.code
        )
        return False

    last_modified = _parse_last_modified(head_resp)
    feed_id = f"{provider.code} ({last_modified.strftime('%Y-%m-%d %H:%M:%S %Z')})"

    # Everything from here on mutates the DB: flipping the previous current
    # feed, creating the new one, and importing every table. Wrap it all in
    # one transaction so a failure partway through (e.g. a table that fails
    # bulk_create) rolls back cleanly instead of leaving a half-imported
    # Feed marked is_current=True. The HTTP + etag comparison above stays
    # outside the transaction since it does no DB writes.
    try:
        with transaction.atomic():
            if current_feed is not None:
                current_feed.is_current = False
                current_feed.save(update_fields=["is_current"])

            feed = Feed.objects.create(
                feed_id=feed_id,
                http_etag=new_tag,
                http_last_modified=last_modified,
                is_current=True,
                feed_publisher=provider,
            )

            for table_name, model in _TABLES:
                count = _import_table(table_name, model, schedule_zip, feed)
                logger.info(
                    "Imported %d rows into %s for feed %s", count, table_name, feed_id
                )
    except Exception:
        logger.exception(
            "Import failed for provider %s; rolled back feed %s", provider.code, feed_id
        )
        return False

    return True
