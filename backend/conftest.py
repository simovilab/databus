"""
pytest configuration for the backend Django project.
Sets required environment variables before Django settings load.
"""
import os

# Django core
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

# Database (unused by SimpleTestCase-based realtime tests, but required by settings)
os.environ.setdefault("DB_NAME", "databus")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")

# Redis (realtime views mock this, but settings module requires it)
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")

# macOS: GDAL/GEOS paths (Homebrew defaults — adjust if installed elsewhere)
import platform
if platform.system() == "Darwin":
    os.environ.setdefault(
        "GDAL_LIBRARY_PATH",
        "/opt/homebrew/lib/libgdal.dylib",
    )
    os.environ.setdefault(
        "GEOS_LIBRARY_PATH",
        "/opt/homebrew/lib/libgeos_c.dylib",
    )
