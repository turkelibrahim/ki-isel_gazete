"""Celery Beat schedule for automated news data fetching."""

from __future__ import annotations

from celery.schedules import crontab

timezone = "Europe/Istanbul"
enable_utc = True
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

beat_schedule = {
    "fetch-breaking-news-every-5-minutes": {
        "task": "app.tasks.fetch_tasks.fetch_breaking_news",
        "schedule": crontab(minute="*/5"),
    },
    "fetch-all-rss-hourly": {
        "task": "app.tasks.fetch_tasks.fetch_all_rss",
        "schedule": crontab(minute=0),
    },
    "full-web-crawl-daily-0600-istanbul": {
        "task": "app.tasks.fetch_tasks.full_crawl",
        "schedule": crontab(hour=6, minute=0),
    },
    "rebuild-duplicate-index-daily": {
        "task": "app.tasks.dedup_task.rebuild_duplicate_index",
        "schedule": crontab(hour=3, minute=30),
    },
    "active-learning-retrain-daily": {
        "task": "app.tasks.retrain_tasks.retrain_models_if_needed",
        "schedule": crontab(hour=4, minute=15),
    },
    "generate-daily-personal-newspapers-0700": {
        "task": "app.tasks.edition_tasks.generate_daily_editions",
        "schedule": crontab(hour=7, minute=0),
    },
    "send-event-reminders-every-15-minutes": {
        "task": "app.tasks.reminder_task.send_event_reminders",
        "schedule": crontab(minute="*/15"),
    },
    "refresh-trending-cache-every-10-minutes": {
        "task": "app.tasks.trending_tasks.refresh_trending_cache",
        "schedule": crontab(minute="*/10"),
    },
    "train-recommender-models-weekly": {
        "task": "app.tasks.recommender_tasks.train_recommender_models",
        "schedule": crontab(day_of_week="sun", hour=3, minute=0),
    },
    "refresh-topic-model-weekly": {
        "task": "app.tasks.topic_tasks.refresh_topic_model",
        "schedule": crontab(day_of_week="sun", hour=4, minute=0),
    },

}

