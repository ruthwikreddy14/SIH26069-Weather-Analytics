-- Initialize PostGIS extension and create database schema
-- Run this script after creating the PostgreSQL database

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verify PostGIS installation
SELECT PostGIS_version();

-- Note: Tables will be created automatically by SQLAlchemy
-- This script only ensures the required extensions are available

-- Optional: Create indexes for common queries (SQLAlchemy will handle this)
-- But we can add additional spatial indexes here if needed

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';
