# SIH26069 Weather Analytics Platform - Backend

Backend API for the National Weather Big Data Analytics Platform.

## Tech Stack

- **FastAPI** - Modern async Python web framework
- **PostgreSQL + PostGIS** - Spatial database for geospatial queries
- **Redis** - Caching and task queue broker
- **SQLAlchemy** - Async ORM
- **Pydantic** - Data validation

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Docker & Docker Compose (for PostgreSQL and Redis)

### 2. Start Database Services

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 3. Install Python Dependencies

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and update if needed (default values work for local development).

### 5. Run the Backend

```bash
# From the backend directory
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Access the API

- **API Docs (Swagger):** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Root:** http://localhost:8000/

## Project Structure

```
backend/
├── app/
│   ├── api/              # API route handlers
│   │   ├── health.py     # Health check endpoint
│   │   └── __init__.py
│   ├── core/             # Core configuration
│   │   ├── config.py     # Settings management
│   │   ├── database.py   # Database connection
│   │   └── redis_client.py
│   ├── models/           # SQLAlchemy ORM models
│   │   └── weather_report.py
│   ├── schemas/          # Pydantic schemas
│   │   └── health.py
│   └── main.py           # FastAPI application
├── requirements.txt      # Python dependencies
└── README.md
```

## Database Models

- **WeatherReport** - Main table for weather reports from all sources
- **EventCluster** - Clusters of duplicate/similar reports
- **VerificationLog** - Audit log of verification steps
- **AdminUser** - Admin users for the platform

## API Endpoints

### Health Check
- `GET /health` - Check if all services are operational

### Coming Soon
- `POST /api/reports/submit` - Submit a new weather report
- `GET /api/reports` - Query weather reports with filters
- `GET /api/analytics/*` - Analytics endpoints

## Development

### Database Migrations

The application uses SQLAlchemy's `Base.metadata.create_all()` to automatically create tables on startup. For production, consider using Alembic for migrations.

### Stopping Services

```bash
# Stop backend (Ctrl+C in terminal)

# Stop Docker services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

## Troubleshooting

### Database Connection Error
- Ensure Docker services are running: `docker-compose ps`
- Check PostgreSQL logs: `docker-compose logs postgres`

### Redis Connection Error
- Check Redis logs: `docker-compose logs redis`
- Test Redis: `docker exec -it weather-redis redis-cli ping`

### PostGIS Not Found
- The PostGIS extension is automatically installed with the `postgis/postgis` Docker image
- Verify: Connect to DB and run `SELECT PostGIS_version();`
