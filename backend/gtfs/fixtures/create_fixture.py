import pandas as pd
import json
import sys
import os
import django

# Set the DJANGO_SETTINGS_MODULE environment variable
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datahub.settings")

# Add the project directory to the sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Setup Django
django.setup()

from datetime import datetime
from django.db.models import (
    DateField,
    IntegerField,
    FloatField,
    DecimalField,
    ForeignKey,
)
from django.apps import apps
from gtfs.models import *

# Initialize a dictionary to hold the model field mappings
model_field_mapping = {}

# Get all models from the 'gtfs' app
gtfs_models = apps.get_app_config("gtfs").get_models()

# Iterate over each model and retrieve its field names
for model in gtfs_models:
    model_name = model._meta.model_name
    field_names = [
        field.name
        for field in model._meta.get_fields()
        if field.concrete and not field.many_to_many and field.name != "id"
    ]
    model_field_mapping[model_name] = field_names

# Print the model field mappings (used for debugging)
# print(model_field_mapping["agency"])

# Path to your Excel file
script_dir = os.path.dirname(os.path.abspath(__file__))
excel_file_path = os.path.join(script_dir, "UCR_bus_GTFS_v2024_2.xlsx")

# Mapping of Excel tab names to Django model names and their fields in ../../models.py
# The mapping is: 'excel_tab': (app_name.model_name, model_field_mapping["model_name"])
tab_to_model_mapping = {
    "agency": ("gtfs.agency", model_field_mapping["agency"]),
    "routes": ("gtfs.route", model_field_mapping["route"]),
    "calendar": ("gtfs.calendar", model_field_mapping["calendar"]),
    "calendar_dates": ("gtfs.calendardate", model_field_mapping["calendardate"]),
    "stops": ("gtfs.stop", model_field_mapping["stop"]),
    "stop_times": ("gtfs.stoptime", model_field_mapping["stoptime"]),
    "fare_attributes": ("gtfs.fareattribute", model_field_mapping["fareattribute"]),
    "fare_rules": ("gtfs.farerule", model_field_mapping["farerule"]),
    "shapes": ("gtfs.shape", model_field_mapping["shape"]),
    "trips": ("gtfs.trip", model_field_mapping["trip"]),
    "GEOSHAPES": ("gtfs.geoshape", model_field_mapping["geoshape"]),
}


# Read the Excel file
xls = pd.ExcelFile(excel_file_path)

# Maximum number of rows to process from each sheet
# Set to None to process all rows (used for debugging)
max_rows_per_sheet = ""

# Initialize an empty list for fixtures
fixtures = []

# Initialize a counter for primary keys
# pk_counter = 2  # Start at 2 to avoid conflicts with the existing fixtures

# Process each sheet in the Excel file
for sheet_name in xls.sheet_names:
    pk_counter = 1  # Start at 2 to avoid conflicts with the existing fixtures
    df = pd.read_excel(xls, sheet_name)

    # Limit the number of rows if max_rows_per_sheet is set
    if isinstance(max_rows_per_sheet, (int)) and max_rows_per_sheet != 0:
        df = df.head(max_rows_per_sheet)

    model_info = tab_to_model_mapping.get(sheet_name)

    if model_info:
        model_name, model_fields = model_info
        custom_model_name = model_name.split(".")[1]
        model_class = apps.get_model(app_label="gtfs", model_name=custom_model_name)

        # Print model fields for debugging
        print(f"Model fields for {model_name}: {model_fields}")

        for index, row in df.iterrows():
            fields_data = {}
            # Managing some field format exeptions
            for field in model_fields:
                # Set the field type
                field_type = model_class._meta.get_field(field)
                field_value = row.get(field, None)

                # Convert NaN to None
                if pd.isna(field_value) or field_value == "":
                    field_value = None

                if isinstance(field_type, DateField):
                    # Convert the string to a date object
                    field_value = (
                        datetime.strptime(str(field_value), "%Y%m%d").date().isoformat()
                        if field_value or field_value != ""
                        else None
                    )
                    fields_data[field] = field_value
                elif field_type.get_internal_type() == "PointField":
                    # Convert the string to a Point object
                    if field_value or field_value != "":
                        # point_str = field_value.split('POINT (')[1].strip(')')
                        # longitude, latitude = map(float, point_str.split())
                        # fields_data[field] = (longitude,latitude)
                        fields_data[field] = field_value
                    else:
                        fields_data[field] = None
                elif field_type.get_internal_type() == "IntegerField":
                    # Convert the string to an integer
                    fields_data[field] = (
                        int(field_value) if field_value is not None else None
                    )
                elif field_type.get_internal_type() == "FloatField":
                    # Convert the string to a float
                    fields_data[field] = float(field_value) if field_value else None
                elif field_type.get_internal_type() == "CharField":
                    # Convert the string to a char
                    fields_data[field] = str(field_value) if field_value else None
                elif field_type.get_internal_type() == "TextField":
                    # Convert the string to a text
                    fields_data[field] = str(field_value) if field_value else None
                elif field_type.get_internal_type() == "TimeField":
                    # Convert the string to a time object
                    if field_value:
                        try:
                            fields_data[field] = (
                                datetime.strptime(str(field_value), "%H:%M:%S")
                                .time()
                                .isoformat()
                            )
                        except ValueError:
                            fields_data[field] = (
                                datetime.strptime(str(field_value), "%H:%M:%S.%f")
                                .time()
                                .isoformat()
                            )
                    else:
                        fields_data[field] = None
                elif isinstance(field_type, ForeignKey):
                    # Handle ForeignKey fields
                    related_model_name = field_type.related_model._meta.model_name
                    related_pk = row.get(f"{field}_id", None)
                    fields_data[field] = (
                        related_pk if related_pk else 1
                    )  # Default to 1 if no related_pk
                # elif field_type.get_internal_type() == "ForeignKey":
                # Get the related model name
                #    related_model_name = field_type.related_model._meta.model_name
                # Get the related model's primary key
                #    related_pk = row.get(f"{field}_id", None)
                # Set the field value to the related model's primary key
                #    fields_data[field] = related_pk
                else:
                    # Set the field value to the row's value
                    fields_data[field] = field_value

            # Add a fixed field 'feed' with a value of "1" for 'gtfs.stop' and 'gtfs.route'
            if "feed" in model_fields:
                fields_data["feed"] = "1"
            if "pickup_type" in model_fields:
                fields_data["pickup_type"] = 0
            if "drop_off_type" in model_fields:
                fields_data["drop_off_type"] = 0

            # Assign geoshape based on shape_id
            if "geoshape" in model_fields and "shape_id" in row:
                shape_id = row["shape_id"]
                if shape_id == "desde_educacion_sin_milla":
                    fields_data["geoshape"] = 1
                elif shape_id == "desde_educacion_con_milla":
                    fields_data["geoshape"] = 2
                elif shape_id == "desde_artes_sin_milla":
                    fields_data["geoshape"] = 3
                elif shape_id == "desde_artes_con_milla":
                    fields_data["geoshape"] = 4
                elif shape_id == "hacia_artes":
                    fields_data["geoshape"] = 5
                elif shape_id == "hacia_educacion":
                    fields_data["geoshape"] = 6

            # if "parent_station" in model_fields and fields_data.get("parent_station") is None:
            #    fields_data["parent_station"] = "Estacion Principal"  # or some default value
            # if "stop_timezone" in model_fields and fields_data.get("stop_timezone") is None:
            #    fields_data["stop_timezone"] = ""  # or some default value

            # Ensure all other fields are not null
            for key in fields_data:
                if (
                    fields_data[key] is None
                    and not isinstance(model_class._meta.get_field(key), IntegerField)
                    and not isinstance(model_class._meta.get_field(key), FloatField)
                    and not isinstance(model_class._meta.get_field(key), DecimalField)
                ):
                    fields_data[key] = ""

            fixture = {"model": model_name, "pk": pk_counter, "fields": fields_data}
            fixtures.append(fixture)
            pk_counter += 1  # Increment the pk counter for the next fixture

# Additional data to be added. These are not part of the Excel file but needed for other models to work
additional_data = [
    {
        "model": "gtfs.gtfsprovider",
        "pk": 1,
        "fields": {
            "code": "bUCR",
            "name": "bUCR",
            "description": "Bus de la UCR",
            "website": "https://bucr.digital",
            "schedule_url": None,
            "trip_updates_url": None,
            "vehicle_positions_url": None,
            "service_alerts_url": None,
            "timezone": "America/costa_rica",
            "is_active": True,
        },
    },
    {
        "model": "gtfs.feed",
        "pk": 1,
        "fields": {
            "provider": 1,
            "http_etag": None,
            "http_last_modified": "2024-07-11T00:00:00Z",
            "is_current": True,
            "retrieved_at": "2024-07-11T04:28:41.332Z",
        },
    },
]

# Append the additional data to the fixtures list
fixtures.extend(additional_data)

# Write fixtures to a file
json_file_path = os.path.join(script_dir, "gtfs.json")
with open(json_file_path, "w") as f:
    json.dump(fixtures, f, ensure_ascii=False, indent=4)
