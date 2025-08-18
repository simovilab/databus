from django.shortcuts import render
from django.conf import settings
from django.http import FileResponse
from django.views.decorators.clickjacking import xframe_options_exempt

# Create your views here.


def status(request):
    return render(request, "status.html")


def schedule(request):
    file_path = settings.BASE_DIR / "feed" / "files" / "bUCR_GTFS.zip"
    return FileResponse(open(file_path, "rb"), filename="bUCR_GTFS.zip")


@xframe_options_exempt
def vehicle_json(request):
    file_path = settings.BASE_DIR / "feed" / "files" / "vehicle_positions.json"
    return FileResponse(open(file_path, "rb"), filename="vehicle_positions.json")


@xframe_options_exempt
def vehicle_pb(request):
    file_path = settings.BASE_DIR / "feed" / "files" / "vehicle_positions.pb"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="vehicle_positions.pb"
    )


@xframe_options_exempt
def trip_updates_json(request):
    file_path = settings.BASE_DIR / "feed" / "files" / "trip_updates.json"
    return FileResponse(open(file_path, "rb"), filename="trip_updates.json")


@xframe_options_exempt
def trip_updates_pb(request):
    file_path = settings.BASE_DIR / "feed" / "files" / "trip_updates.pb"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="trip_updates.pb"
    )
