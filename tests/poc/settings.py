import os

SECRET_KEY = "local-ulid-investigation"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
INSTALLED_APPS = ["poc"]
test_database = os.environ.get("ULID_TEST_DATABASE", "sqlite")
if test_database == "sqlite":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
elif test_database == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("ULID_POSTGRES_DB", "ulid_test"),
            "USER": os.environ.get("ULID_POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("ULID_POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("ULID_POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.environ.get("ULID_POSTGRES_PORT", "5432"),
        }
    }
else:
    raise ValueError(f"Unsupported test database: {test_database}")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "poc.urls"
USE_TZ = True
MIDDLEWARE = []
