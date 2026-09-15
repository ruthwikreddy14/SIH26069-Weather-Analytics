"""
Quick script to check GPS data in database
"""
import asyncio
from sqlalchemy import select, text
from app.core.database import AsyncSessionLocal
from app.models.weather_report import WeatherReport
from geoalchemy2.shape import to_shape

async def check_gps():
    async with AsyncSessionLocal() as session:
        # Get first 3 reports
        result = await session.execute(
            select(WeatherReport).limit(3)
        )
        reports = result.scalars().all()
        
        print(f"\n=== Checking {len(reports)} reports ===\n")
        
        for report in reports:
            print(f"Report ID: {report.id}")
            print(f"City: {report.city}, State: {report.state}")
            print(f"Location column type: {type(report.location)}")
            print(f"Location column value: {report.location}")
            
            if report.location:
                try:
                    # Try to extract GPS
                    point = to_shape(report.location)
                    print(f"✓ GPS extracted: lat={point.y}, lon={point.x}")
                except Exception as e:
                    print(f"✗ GPS extraction failed: {e}")
            else:
                print(f"✗ No location data in database")
            
            print("-" * 60)

if __name__ == "__main__":
    asyncio.run(check_gps())
