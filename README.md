<img width="250" alt="databus" src="https://github.com/user-attachments/assets/b2ad45ac-83e5-44cf-a93e-898868763530" />

# Databús

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

## 🛣️ Roadmap

Where is this going? Check SIMOVI's [roadmap](https://github.com/simovilab/context/blob/main/roadmap.md).

## 🤝 Contributing

Help is welcome! See the [guidelines](https://github.com/simovilab/.github/blob/main/CONTRIBUTING.md).

## 📞 Contact

- Email: simovi@ucr.ac.cr
- Website: [simovi.org](https://simovi.org)

## 📄 License

Apache 2.0
