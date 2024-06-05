import requests
from decouple import config

url = "http://localhost:3456/api/path/"

token = config("API_TOKEN")
data = {
    "trip": 1,
    "current_stop_sequence": 5,
    "stop_id": "5",
    "current_status": "INCOMING_AT",
    "congestion_level": "STOP_AND_GO",
}
headers = {
    "Authorization": f"Token {token}",
    "Content-Type": "application/json",
}
response = requests.post(url, json=data, headers=headers)

if response.status_code == 201:
    print("POST was successful.")
else:
    print(f"POST failed. Status code: {response.status_code}.")