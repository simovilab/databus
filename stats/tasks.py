from celery import shared_task

from feed.models import Journey, Position, Progression
from .models import EstimationModel


@shared_task
def update_estimation_models():
    return "Estimation model updated"
