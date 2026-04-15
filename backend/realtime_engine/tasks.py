from celery import shared_task


@shared_task(queue="realtime_engine")
def hello_world():
    print("Hello, world!")
