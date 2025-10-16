from celery import shared_task


@shared_task
def ping():
    print("🏓 Celery ping executed successfully!")
    return "pong"
