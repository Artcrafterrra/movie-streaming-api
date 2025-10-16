import os
from celery import Celery
from config.settings import base_app_settings as settings


print("=== Celery Configuration Check ===")
print(f"Redis URL: {settings.REDIS_URL}")
print(f"Database URL: {settings.DATABASE_URL}")
print(f"Environment: {settings.ENVIRONMENT}")
print("===================================")


celery_app = Celery(
    "movie_streaming_api",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)


celery_app.autodiscover_tasks(packages=["src.tasks"], force=True)

try:
    import src.tasks.ping_task  # noqa
    import src.tasks.cleanup_tokens  # noqa

    print("✅ Tasks imported manually to ensure registration.")
except ImportError as e:
    print(f"⚠️ Could not import task modules: {e}")


celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "delete-expired-tokens-every-hour": {
        "task": "src.tasks.cleanup_tokens.delete_expired_tokens",
        "schedule": 3600,
    },
}


print(f"Registered tasks: {list(celery_app.tasks.keys())}")
