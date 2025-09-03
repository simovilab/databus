import requests

api = "https://realtime.bucr.digital/api/"
token = "ad936c7ae11a9b96e55bc3c54a91972f9896a854"
headers = {
    "Authorization": f"Token {token}",
    "Content-Type": "application/x-www-form-urlencoded",
}

journey = {
    "vehicle": "SJB1234",
    "equipment": "2d01a00e-6287-4bfe-8a2b-7bc8a4e2aa5c",
    "operator": "1-1234-5678",
    "trip_id": "desde_educacion_con_milla_entresemana_13:33",
    "route_id": "bUCR_L1",
    "direction_id": 0,
    "start_time": "13:33:06",
    "start_date": "2024-08-29",
    "schedule_relationship": "SCHEDULED",
    "shape_id": "desde_educacion_con_milla",
    "journey_status": "IN_PROGRESS",
}

api_url = f"{api}journey/"
response = requests.post(api_url, data=journey, headers=headers)
journey_id = response.json()["id"]
print(f"Journey: {journey_id}")

endpoints = {}

endpoints["position"] = {
    "journey": journey_id,
    "timestamp": "2024-08-29T13:35:55-06:00",
    # "point": "SRID=4326;POINT (-84.04555530733563 9.93540698388418)",
    "latitude": 9.93540698388418,
    "longitude": -84.04555530733563,
    "bearing": 0.0,
    "odometer": 9.0,
    "speed": 12.0,
}

endpoints["progression"] = {
    "journey": journey_id,
    "timestamp": "2024-08-29T13:36:29.055000-06:00",
    "current_stop_sequence": 3,
    "stop_id": "bUCR_0_04",
    "current_status": "INCOMING_AT",
    "congestion_level": "RUNNING_SMOOTHLY",
}

endpoints["occupancy"] = {
    "journey": journey_id,
    "timestamp": "2024-08-29T13:36:44.101000-06:00",
    "occupancy_status": "CRUSHED_STANDING_ROOM_ONLY",
    "occupancy_percentage": 81,
    "occupancy_count": 35,
}

for endpoint in endpoints:
    api_url = f"{api}{endpoint}/"
    response = requests.post(api_url, data=endpoints[endpoint], headers=headers)
    # Show response code
    print(f"{endpoint}: {response.status_code}")
