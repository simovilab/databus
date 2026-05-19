<img width="250" alt="databus" src="https://github.com/user-attachments/assets/b2ad45ac-83e5-44cf-a93e-898868763530" />

# Databús

![Static Badge](https://img.shields.io/badge/web_framework-Django-white?logo=django)
![Static Badge](https://img.shields.io/badge/package_manager-uv-white?logo=uv)

Core backend server implementing GTFS Schedule and GTFS Realtime specifications for comprehensive transit data management. Provides RESTful API endpoints for static schedule data (routes, stops, trips) and real-time vehicle information (positions, alerts, service updates) with PostgreSQL/PostGIS storage and real-time data validation.

## ✨ Features

- 🚌 **GTFS Schedule & Realtime Support** - Full implementation of GTFS specifications
- 🌐 **RESTful API** - Comprehensive endpoints for transit data access
- 📊 **Real-time Data Processing** - Live vehicle positions, alerts, and service updates
- 🗺️ **Geospatial Support** - PostgreSQL/PostGIS for location-based queries
- 🔄 **Background Processing** - Celery integration for data validation and updates
- 🏢 **Multi-tenant Architecture** - Support for multiple transit agencies

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Redis server
- PostgreSQL 12+ with PostGIS extension
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/simovilab/databus.git
   cd databus
   ```

2. **Set up virtual environment** (recommended)

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**

   ```bash
   cp .env.example .env  # Create and edit your environment variables
   ```

5. **Set up database**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser  # Optional: create admin user
   ```

### Running the Application

1. **Start Redis server** (in separate terminal)

   ```bash
   redis-server
   ```

2. **Start Celery worker** (in separate terminal)

   ```bash
   celery -A realtime worker -l info
   ```

3. **Start Django development server**
   ```bash
   python manage.py runserver
   ```

The application will be available at `http://localhost:8000`

## 🚀 Usage

| Endpoint            | Description                                    |
| ------------------- | ---------------------------------------------- |
| `/api/`             | REST API root - browse all available endpoints |
| `/api/docs/`        | Interactive API documentation (ReDoc)          |
| `/api/docs/schema/` | OpenAPI schema                                 |
| `/admin/`           | Django admin interface                         |
| `/feed/`            | GTFS feed endpoints                            |

## 📚 Documentation

- **[HOWTO.md](HOWTO.md)** - Complete guide for setting up a development environment with Docker
- **[docs/development.md](docs/development.md)** - Functional development notes and data specifications (Spanish)
- **[docs/deployment.md](docs/deployment.md)** - Production deployment with Celery and systemd
- **[docs/api.md](docs/api.md)** - API specification and data formats
- **[docs/obe.md](docs/obe.md)** - On-board equipment specifications
- **[WARP.md](WARP.md)** - Development guidance for Warp terminal users

For the full documentation site, run `mkdocs serve` and visit http://localhost:8000

## Demo: full run lifecycle

End-to-end demo of a complete run lifecycle driven by MQTT telemetry from the simulator.

```bash
# Terminal 1 — start the full databus stack
cd databus && bash scripts/dev.sh

# Terminal 2 — load GTFS feed + bootstrap simulator-aligned runs
docker compose -f compose.dev.yml exec orchestrator \
    uv run python manage.py loaddata gtfs.json
docker compose -f compose.dev.yml exec orchestrator \
    uv run python manage.py bootstrap_simulator_runs

# Terminal 3 — start the simulator (wired to databus broker)
cd ../simulator && docker compose up simulator web

# Terminal 4 — observe (optional)
open http://localhost:8080                      # live map
watch ls backend/feed/files/                   # GTFS-RT outputs (refresh every 15 s)
```

Within ~30 s of starting the simulator:

- Every run advances `CONFIRMED → TRACKING → IN_PROGRESS`
- `backend/feed/files/vehicle_positions.pb` contains one `FeedEntity` per active run
- `backend/feed/files/trip_updates.pb` contains stop-time predictions

Killing the simulator triggers `RUN_TRACKING_LOST` after 60 s and
`RUN_TRACKING_EXPIRED → CANCELLED` after 300 s.

Verify the protobuf output:

```python
from google.transit import gtfs_realtime_pb2
msg = gtfs_realtime_pb2.FeedMessage()
msg.ParseFromString(open("backend/feed/files/vehicle_positions.pb", "rb").read())
print(len(msg.entity))  # should equal the number of active runs
```

## 🛣️ Roadmap

Where is this going? Check SIMOVI's [roadmap](https://github.com/simovilab/context/blob/main/roadmap.md).

## 🤝 Contributing

Help is welcome! See the [guidelines](https://github.com/simovilab/.github/blob/main/CONTRIBUTING.md).

## 📞 Contact

- Email: simovi@ucr.ac.cr
- Website: [simovi.org](https://simovi.org)

## 📄 License

Apache 2.0
