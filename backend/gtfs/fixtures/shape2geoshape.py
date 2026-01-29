import json
from collections import defaultdict

# Read the shapes.json file
with open("shapes.json", "r") as file:
    shapes_data = json.load(file)

# Group entries by shape_id
shapes_dict = defaultdict(list)
for entry in shapes_data:
    shape_id = entry["fields"]["shape_id"]
    lat = entry["fields"]["shape_pt_lat"]
    lon = entry["fields"]["shape_pt_lon"]
    shapes_dict[shape_id].append((lon, lat))

# Create the new JSON structure
new_shapes_data = []
pk_counter = 1

for shape_id, points in shapes_dict.items():
    geometry = (
        "SRID=4326;LINESTRING ("
        + ", ".join(f"{lon} {lat}" for lon, lat in points)
        + ")"
    )
    new_entry = {
        "model": "gtfs.geoshape",
        "pk": pk_counter,
        "fields": {
            "feed": shapes_data[0]["fields"][
                "feed"
            ],  # Assuming all entries have the same feed
            "shape_id": shape_id,
            "geometry": geometry,
            "has_altitude": False,
        },
    }
    new_shapes_data.append(new_entry)
    pk_counter += 1

# Write the new JSON structure to a new file
with open("geoshapes.json", "w") as file:
    json.dump(new_shapes_data, file, indent=4)
