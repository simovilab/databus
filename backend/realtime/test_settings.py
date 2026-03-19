"""
Test settings for pytest-django.
Sets os.environ defaults BEFORE importing main settings so that
python-decouple's config() calls resolve correctly without a .env file.
"""
import os
import platform

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

os.environ.setdefault("DB_NAME", "databus")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")

os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")

if platform.system() == "Darwin":
    os.environ.setdefault("GDAL_LIBRARY_PATH", "/usr/local/lib/libgdal.dylib")
    os.environ.setdefault("GEOS_LIBRARY_PATH", "/usr/local/lib/libgeos_c.dylib")

from realtime.settings import *  # noqa: E402, F401, F403
