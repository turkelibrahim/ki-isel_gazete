"""Celery task package."""

from . import dedup_task as dedup_task
from . import edition_tasks as edition_tasks
from . import fetch_tasks as fetch_tasks
from . import retrain_tasks as retrain_tasks
from . import reminder_task as reminder_task
from . import trending_tasks as trending_tasks
from . import recommender_tasks as recommender_tasks
from . import topic_tasks as topic_tasks
