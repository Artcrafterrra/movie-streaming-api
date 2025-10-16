from celery import Celery
from config.settings import base_app_settings as settings

# === Debug output при старті ===
print("=== Celery Configuration Check ===")
print(f"Redis URL: {settings.REDIS_URL}")
print(f"Database URL: {settings.DATABASE_URL}")
print(f"Environment: {settings.ENVIRONMENT}")
print("===================================")

celery_app = Celery(
    "theater",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "delete-expired-tokens-every-hour": {
        "task": "src.tasks.cleanup_tokens.delete_expired_tokens",
        "schedule": 3600.0,  # кожну годину
    },
}

celery_app.autodiscover_tasks(["src.tasks"])
