"""
Test script to verify all imports work correctly.
Run this to check if the backend structure is valid.
"""

def test_imports():
    """Test that all modules can be imported."""
    
    print("Testing imports...")
    
    try:
        print("✓ Importing core config...")
        from app.core.config import settings
        print(f"  - App Name: {settings.APP_NAME}")
        print(f"  - Version: {settings.APP_VERSION}")
        
        print("✓ Importing database...")
        from app.core.database import Base, get_db
        
        print("✓ Importing Redis client...")
        from app.core.redis_client import redis_client
        
        print("✓ Importing models...")
        from app.models import WeatherReport, EventCluster, VerificationLog, AdminUser
        print(f"  - WeatherReport table: {WeatherReport.__tablename__}")
        print(f"  - EventCluster table: {EventCluster.__tablename__}")
        print(f"  - VerificationLog table: {VerificationLog.__tablename__}")
        print(f"  - AdminUser table: {AdminUser.__tablename__}")
        
        print("✓ Importing schemas...")
        from app.schemas import HealthResponse
        
        print("✓ Importing API routes...")
        from app.api import api_router
        
        print("✓ Importing main app...")
        from app.main import app
        print(f"  - Title: {app.title}")
        print(f"  - Version: {app.version}")
        
        print("\n✅ All imports successful!")
        print("\nBackend structure is valid and ready for deployment.")
        return True
        
    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_imports()
    exit(0 if success else 1)
