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

## ✨ Features

### 🏭 **Production Infrastructure**
- **Containerized Deployment**: Docker-based dev/production environments
- **Scalable Architecture**: Nginx reverse proxy with load balancing ready
- **High Availability**: Redis-backed caching and session management
- **Security Hardened**: Rate limiting, security headers, and container isolation
- **Monitoring Ready**: Health check endpoints and structured logging

### 📡 **Real-time Data Processing**
- **GTFS Realtime Integration**: Vehicle positions, trip updates, and service alerts
- **Background Task Processing**: Celery-powered async data collection
- **Geospatial Analysis**: PostGIS-enabled location-based services
- **Data Validation**: Robust data quality checks and error handling
- **Multi-source Aggregation**: Unified data from various transit agencies

### 🖥️ **Display Management**
- **Geographic Screen Positioning**: GPS-coordinated display locations
- **Dynamic Content Rendering**: Context-aware information display
- **WebSocket Live Updates**: Real-time screen content synchronization
- **Kiosk Mode Support**: Raspberry Pi deployment optimizations
- **Responsive Design**: Multi-device and screen size support

## 🛠️ Technology Stack

### 🔋 **Backend & APIs**
- **Django 5.2+**: Modern Python web framework with GeoDjango/PostGIS
- **Django REST Framework**: RESTful API development
- **Django Channels**: WebSocket support for real-time features
- **Daphne ASGI Server**: Production-ready async server
- **Python 3.12+**: Latest Python with modern async support

### 📊 **Data & Storage**
- **PostgreSQL 16**: Primary database with ACID compliance
- **PostGIS 3.4**: Advanced geospatial data processing
- **Redis 7**: High-performance caching and message broker
- **Docker Volumes**: Persistent data storage

### 🚪 **Infrastructure & Deployment**
- **Docker & Docker Compose**: Containerized development and production
- **Nginx**: Reverse proxy with security headers and rate limiting
- **Multi-stage Builds**: Optimized container images
- **uv**: Fast Python package management

### 🌐 **Real-time & Background Processing**
- **Celery**: Distributed task processing
- **Celery Beat**: Periodic task scheduling
- **WebSockets**: Live data streaming to displays
- **GTFS Realtime**: Transit data processing bindings

### 🔒 **Security & Monitoring**
- **Environment-based Config**: Secure secrets management
- **Rate Limiting**: API and admin protection
- **Security Headers**: OWASP recommended protections
- **Health Checks**: Application and service monitoring

## 🚀 Quick Start

### Prerequisites
- **Docker Desktop** ([Download](https://www.docker.com/products/docker-desktop))
- **Git** ([Download](https://git-scm.com/downloads))
- **8GB+ RAM** recommended for all services

### 🛠️ Development Setup (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/simovilab/infobus.git
   cd infobus
   ```

2. **Initialize submodules**
   ```bash
   git submodule update --init --recursive
   ```

3. **Start development environment**
   ```bash
   ./scripts/dev.sh
   ```

   This single command will:
   - 📦 Build all Docker containers
   - 💾 Set up PostgreSQL with PostGIS
   - 🔄 Start Redis for caching
   - ⚙️ Run database migrations
   - 👥 Create admin user (admin/admin)
   - 🌐 Launch the development server with hot reload

4. **Access the application**
   - **Website**: http://localhost:8000
   - **Admin Panel**: http://localhost:8000/admin (admin/admin)
   - **API**: http://localhost:8000/api/

### 🏭 Production Deployment

1. **Configure production environment**
   ```bash
   # Copy and edit production settings
   cp .env.prod.example .env.prod
   # Generate a secure SECRET_KEY
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

2. **Start production environment**
   ```bash
   ./scripts/prod.sh
   ```

   Production includes:
   - 🌐 Nginx reverse proxy with SSL-ready config
   - 🛡️ Security headers and rate limiting
   - 📊 Performance optimizations and caching
   - 🔍 Health check endpoints

3. **Access production**
   - **Website**: http://localhost (via Nginx)
   - **Admin**: http://localhost/admin
   - **Health Check**: http://localhost/health/

### 📝 Common Commands

```bash
# View logs
docker-compose logs -f

# Run Django commands
docker compose exec web uv run python manage.py migrate
docker compose exec web uv run python manage.py createsuperuser
docker compose exec web uv run python manage.py shell

# Run tests
docker compose exec web uv run python manage.py test

# Stop all services
docker compose down
```

## 🏧 Architecture

### 📊 Service Architecture

```
🌐 Internet → 🚪 Nginx (Port 81) → 🐍 Django/Daphne (Port 8000)
                                          ↓
                                   💾 PostgreSQL (PostGIS)
                                          ↓
                                   🔴 Redis ← 🐝 Celery Workers/Beat
```

### 🔄 Data Flow

1. **📡 Data Collection**: Celery tasks periodically fetch GTFS Realtime feeds from transit agencies
2. **⚙️ Data Processing**: Information is validated, processed, and classified by screen relevance
3. **📶 Real-time Distribution**: Django Channels WebSockets push live updates to connected displays
4. **🖥️ Display Rendering**: Raspberry Pi devices in kiosk mode render the passenger information

### 💱 Application Structure

- **`website`**: Main site pages, user management, and public interfaces
- **`alerts`**: Screen management, real-time data display via WebSockets
- **`gtfs`**: GTFS Schedule and Realtime data management (submodule: django-app-gtfs)
- **`feed`**: Information service providers and WebSocket consumers
- **`api`**: RESTful API endpoints with DRF integration

## 📚 API Documentation

### REST API Endpoints
- **`/api/`** - Main API endpoints with DRF browsable interface
- **`/api/gtfs/`** - GTFS Schedule and Realtime data
- **`/api/alerts/`** - Screen management and alert systems
- **`/api/weather/`** - Weather information for display locations

### WebSocket Endpoints
- **`/ws/alerts/`** - Real-time screen updates
- **`/ws/feed/`** - Live transit data streaming

## 🛠️ Development

### Project Structure
```
infobus/
├── 📁 scripts/          # Management scripts 
├── 📁 nginx/            # Nginx configuration
├── 📁 datahub/          # Django project settings
├── 📁 website/          # Main web application
├── 📁 alerts/           # Display and alert management
├── 📁 gtfs/             # GTFS data processing 
├── 📁 feed/             # Data feed management
├── 📁 api/              # REST API endpoints
├── 📦 docker-compose.yml              # Development environment
├── 📦 docker-compose.production.yml   # Production environment
├── 📄 Dockerfile         # Multi-stage container build
└── 📄 WARP.md           # AI assistant guidance
```

### Environment Configuration
- **`.env`** - Base configuration (committed)
- **`.env.dev`** - Development overrides (committed)
- **`.env.prod`** - Production template (committed, no secrets)
- **`.env.local`** - Local secrets (git-ignored)

### Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and test with `./scripts/dev.sh`
4. Run security scan: `gitleaks detect --source . --verbose`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## 🏢 Production Deployment

### Deployment Options
- **☁️ Cloud Platforms**: AWS, GCP, Azure with Docker
- **🖥️ VPS Deployment**: Ubuntu/CentOS with Docker Compose
- **🥰 Raspberry Pi**: Kiosk mode for display devices
- **💻 Local Development**: Full-featured local environment

### Security Checklist
- [ ] Generate secure `SECRET_KEY` in production
- [ ] Update database passwords
- [ ] Configure domain names in `ALLOWED_HOSTS`
- [ ] Set up SSL certificates
- [ ] Configure backup strategy
- [ ] Set up monitoring and logging
- [ ] Test health check endpoints

## 💫 Support & Community

### Getting Help
- **Documentation**: See `WARP.md` for detailed guidance
- **Scripts**: Use `./scripts/dev.sh --help` for command help
- **Health Checks**: Monitor `/health/` endpoint in production
- **Logs**: Use `docker-compose logs -f` for troubleshooting

## 📞 Contact

- Email: simovi@ucr.ac.cr
- Website: [simovi.org](https://simovi.org)

## 📄 License

Apache 2.0
