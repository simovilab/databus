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
- 🔬 **Telemetry Simulator** - Test system before deploying real equipment
- 🚏 **Buses as Rolling Sensors** - Ready for "Células TP" project integration
- 🔑 **JWT Authentication** - Secure token-based authentication with RBAC
- 🚦 **Rate Limiting** - Per-client quotas and throttling
- 🎛️ **Admin Dashboard** - Real-time metrics, audit logging, analytics
- 🧪 **Comprehensive Testing** - 70%+ coverage with CI/CD pipeline
- 📦 **TODS Integration** - Transit Operational Data Standard support

📊 **[View Complete Issues Status Report](docs/ISSUES_STATUS_REPORT.md)** - Track all features, implementation status, and documentation

## 🚀 Getting Started

### Prerequisites

- Python 3.14+
- Redis server
- PostgreSQL 18+ with PostGIS extension
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

   Create your environment configuration file:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and set your values:
   ```bash
   # Required settings
   SECRET_KEY=your-secret-key-here
   DEBUG=1
   ALLOWED_HOSTS=localhost,127.0.0.1
   
   # Database
   DB_NAME=realtime
   DB_USER=postgres
   DB_PASSWORD=your-password
   DB_HOST=localhost
   DB_PORT=5432
   
   # Redis
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```
   
   📖 See [Environment Variables Guide](docs/environment-variables.md) for detailed configuration.

5. **Set up database**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser  # Optional: create admin user
   ```

### Running the Application

#### Option A: Docker (Recommended)

The easiest way to run the application with all services:

```bash
# 1. Build Docker images (REQUIRED for first-time setup)
docker-compose build

# 2. Copy environment file
cp .env.example .env

# 3. Edit .env with your settings (database, Redis, JWT secret, etc.)
nano .env

# 4. Start all services
docker-compose up -d

# 5. Create admin user (required for accessing /admin/)
docker-compose exec web python manage.py createsuperuser

# 6. View logs to verify everything is working
docker-compose logs -f web

# Stop services when needed
docker-compose down
```

**⚠️ Important Notes:**

- **First-time setup**: You MUST run `docker-compose build` before starting services
- **After updating dependencies**: Rebuild with `docker-compose build --no-cache`
- **Default admin credentials** (if you need to set them manually):
  ```bash
  docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); admin = User.objects.get(username='admin'); admin.set_password('your-password'); admin.save()"
  ```

**Services included:**
- **web**: Django application (port 8000)
- **db**: PostgreSQL 18 with PostGIS
- **redis**: Redis server
- **worker**: Celery worker
- **beat**: Celery beat scheduler

**Verify services are running:**
```bash
docker-compose ps  # All services should show "Up" or "Up (healthy)"
docker-compose logs worker  # Check for errors
```

#### Option B: Manual Setup

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

## 🧪 Telemetry Simulator

Test the system before installing equipment on real buses using the built-in telemetry simulator.

### Quick Start

```bash
# Setup simulator (first time only)
docker-compose exec web python manage.py makemigrations simulator
docker-compose exec web python manage.py migrate simulator

# Start simulation for all vehicles
docker-compose exec web python manage.py start_simulation --all

# Or use the helper script
./scripts/simulator.sh start --all

# Monitor simulation
docker-compose exec web python manage.py shell
>>> from simulator.models import SimulatedVehicle
>>> SimulatedVehicle.objects.filter(is_active=True)

# Stop simulation
./scripts/simulator.sh stop --all
```

### What It Does

- Simulates vehicle movement along GTFS routes
- Updates position every 10 seconds
- Updates occupancy at each stop
- Generates realistic telemetry data
- Compatible with GTFS Realtime and "Células TP" project

📖 See [Simulator Documentation](docs/simulator.md) for detailed information.

## 🚏 Proyecto Células TP

Databus is designed to support the "Células TP" concept - using buses as rolling sensors that collect telemetry, tracking, and environmental data.

### Supported Data Types

- **Position**: GPS location, speed, bearing (every 10s)
- **Occupancy**: Passenger count, capacity status (at stops)
- **Emissions**: Air quality, CO₂, NOx
- **Conditions**: Temperature, humidity, vehicle status
- **Progression**: Route progress, stop arrival/departure

📖 See [Células TP Documentation](docs/celulas-tp.md) for the complete vision and implementation roadmap.

## 🚀 Usage

| Endpoint            | Description                                    |
| ------------------- | ---------------------------------------------- |
| `/api/`             | REST API root - browse all available endpoints |
| `/api/docs/`        | Interactive API documentation (ReDoc)          |
| `/api/docs/schema/` | OpenAPI schema                                 |
| `/admin/`           | Django admin interface                         |
| `/feed/`            | GTFS feed endpoints                            |

### Documentation

- 📚 [HOWTO - Docker Setup](HOWTO.md) - Complete setup guide
- 🔧 [Environment Variables](docs/environment-variables.md) - Configuration reference
- 🧪 [Telemetry Simulator](docs/simulator.md) - Testing platform
- 🚏 [Células TP Project](docs/celulas-tp.md) - Buses as rolling sensors
- 🌐 [NGSI-LD Compatibility](docs/ngsi-ld-compatibility.md) - Smart City integration
- 📖 [API Documentation](docs/api.md) - Endpoint reference

### 🎛️ Admin Panel

Databus includes a comprehensive admin dashboard for monitoring and managing your transit API:

- **📊 Metrics Dashboard** - Real-time traffic, latency, and error monitoring
- **👥 Client Management** - API client lifecycle, keys, and quotas
- **📝 Audit Logging** - Complete compliance trail of admin actions
- **📈 Analytics** - Charts for traffic patterns and performance
- **🔐 Access Control** - Secure admin interface with full audit trail

Access the admin panel at `/admin/` and the metrics dashboard at `/admin/api/dashboard/`

📖 See [Admin Dashboard Guide](api/ADMIN_DASHBOARD_README.md) for detailed documentation on:
- Viewing traffic and performance metrics
- Managing API clients and quotas
- Reviewing audit logs for compliance
- Setting up alerts and monitoring

### API Features

- **🔑 Client Registry** - Multi-tenant API client management ([docs](api/CLIENT_REGISTRY_README.md))
- **🚦 Rate Limiting** - Per-client quotas and throttling ([docs](api/RATE_LIMITING_README.md))
- **🔒 JWT Authentication** - Secure token-based auth ([docs](api/JWT_AUTH_README.md))
- **⚡ Performance** - Caching, pagination, compression ([docs](api/SECURITY_PERFORMANCE_README.md))
- **🎛️ Admin Dashboard** - Metrics and audit logging ([docs](api/ADMIN_DASHBOARD_README.md))

## 🧪 Testing

Databus has comprehensive test coverage with unit, integration, and contract tests:

- **📊 Coverage**: 70% minimum threshold enforced
- **🔬 Unit Tests**: Serializers, validators, business logic
- **🔗 Integration Tests**: API endpoints, authentication, rate limiting, caching
- **📋 Contract Tests**: OpenAPI schema validation, response formats
- **🤖 CI/CD**: Automated testing, linting, security scanning on every push
- **📈 Reports**: HTML coverage reports, Codecov integration

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run by category
pytest tests/ -m "unit" -v
pytest tests/ -m "integration" -v
pytest tests/ -m "contract" -v

# Run with coverage
pytest tests/ --cov=api --cov=feed --cov=gtfs --cov-report=html

# View coverage report
open htmlcov/index.html
```

📖 See [Testing Guide](docs/testing.md) for detailed documentation on writing tests, using fixtures, and CI/CD pipeline.

## 🛣️ Roadmap

Where is this going? Check SIMOVI's [roadmap](https://github.com/simovilab/context/blob/main/roadmap.md).

## 🤝 Contributing

Help is welcome! See the [guidelines](https://github.com/simovilab/.github/blob/main/CONTRIBUTING.md).

## 📞 Contact

- Email: simovi@ucr.ac.cr
- Website: [simovi.org](https://simovi.org)

## 📄 License

Apache 2.0
