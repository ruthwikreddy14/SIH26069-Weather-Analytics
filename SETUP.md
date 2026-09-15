# Setup Instructions for SIH26069 Backend

## Option 1: Using Docker (Recommended)

If you have Docker Desktop installed:

```bash
# Start services
docker compose up -d

# Check services are running
docker compose ps

# View logs
docker compose logs -f
```

## Option 2: Manual Installation (Without Docker)

### Install PostgreSQL with PostGIS

**Windows:**
1. Download PostgreSQL from https://www.postgresql.org/download/windows/
2. During installation, include the "PostGIS" extension via Stack Builder
3. Create database:
```sql
CREATE DATABASE weather_db;
CREATE USER weather_user WITH PASSWORD 'weather_pass';
GRANT ALL PRIVILEGES ON DATABASE weather_db TO weather_user;

-- Connect to weather_db
\c weather_db

-- Enable PostGIS
CREATE EXTENSION postgis;
CREATE EXTENSION "uuid-ossp";
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib postgis

# Create database
sudo -u postgres psql
CREATE DATABASE weather_db;
CREATE USER weather_user WITH PASSWORD 'weather_pass';
GRANT ALL PRIVILEGES ON DATABASE weather_db TO weather_user;
\c weather_db
CREATE EXTENSION postgis;
CREATE EXTENSION "uuid-ossp";
```

### Install Redis

**Windows:**
- Download from https://github.com/microsoftarchive/redis/releases
- Or use WSL: `wsl sudo apt install redis-server`

**Linux:**
```bash
sudo apt install redis-server
sudo systemctl start redis
```

### Update .env File

If using different credentials, update the `.env` file:
```
DATABASE_URL=postgresql+asyncpg://your_user:your_pass@localhost:5432/your_db
REDIS_URL=redis://localhost:6379/0
```

## Running the Backend

```bash
# 1. Create virtual environment
cd backend
python -m venv venv

# 2. Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
python -m app.main
```

## Testing the Backend

Once running, test these endpoints:

1. **Root:** http://localhost:8000/
2. **Health Check:** http://localhost:8000/health
3. **API Docs:** http://localhost:8000/docs

### Using curl/PowerShell:

```powershell
# Test root endpoint
curl http://localhost:8000/

# Test health check
curl http://localhost:8000/health
```

## Expected Health Check Response

```json
{
  "status": "healthy",
  "app_name": "SIH26069 Weather Analytics Platform",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected",
  "details": {
    "postgis_version": "3.3 USE_GEOS=1 USE_PROJ=1 ...",
    "debug_mode": true
  }
}
```

## Troubleshooting

### "Database connection refused"
- Ensure PostgreSQL is running
- Check credentials in `.env` match your database

### "Redis connection refused"
- Ensure Redis is running
- Windows: Check Redis service in Task Manager
- Linux: `sudo systemctl status redis`

### "PostGIS extension not found"
- Connect to your database: `psql -U weather_user -d weather_db`
- Run: `CREATE EXTENSION IF NOT EXISTS postgis;`

### Port already in use (8000)
- Change `API_PORT` in `.env` to another port (e.g., 8001)
- Or stop the process using port 8000
