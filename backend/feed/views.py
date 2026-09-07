"""Views serving the published GTFS Schedule zip and GTFS Realtime feed files."""

from django.shortcuts import render
from django.conf import settings
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    HttpResponseNotFound,
)
from django.views.decorators.clickjacking import xframe_options_exempt

# Create your views here.


def status(request: HttpRequest) -> HttpResponse:
    """Render the feed status page."""
    return render(request, "status.html")


def schedule(request: HttpRequest) -> HttpResponseBase:
    """Serve the published GTFS Schedule zip, or 404 if it hasn't been exported yet."""
    file_path = settings.BASE_DIR / "feed" / "files" / "gtfs.zip"
    if not file_path.exists():
        return HttpResponseNotFound(
            "GTFS Schedule zip not yet available. "
            "Run 'manage.py export_gtfs' or wait for the hourly Celery task."
        )
    return FileResponse(open(file_path, "rb"), as_attachment=True, filename="gtfs.zip")


@xframe_options_exempt
def vehicle_json(request: HttpRequest) -> HttpResponseBase:
    """Serve the published VehiclePositions feed as JSON."""
    file_path = settings.BASE_DIR / "feed" / "files" / "vehicle_positions.json"
    return FileResponse(open(file_path, "rb"), filename="vehicle_positions.json")


@xframe_options_exempt
def vehicle_pb(request: HttpRequest) -> HttpResponseBase:
    """Serve the published VehiclePositions feed as a protobuf."""
    file_path = settings.BASE_DIR / "feed" / "files" / "vehicle_positions.pb"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="vehicle_positions.pb"
    )


@xframe_options_exempt
def trip_updates_json(request: HttpRequest) -> HttpResponseBase:
    """Serve the published TripUpdates feed as JSON."""
    file_path = settings.BASE_DIR / "feed" / "files" / "trip_updates.json"
    return FileResponse(open(file_path, "rb"), filename="trip_updates.json")


@xframe_options_exempt
def trip_updates_pb(request: HttpRequest) -> HttpResponseBase:
    """Serve the published TripUpdates feed as a protobuf."""
    file_path = settings.BASE_DIR / "feed" / "files" / "trip_updates.pb"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="trip_updates.pb"
    )
