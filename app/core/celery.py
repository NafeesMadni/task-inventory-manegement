from celery import Celery

from app.core.config import get_settings

celery_app: Celery = Celery(
    main="celery_tasks",
    broker=get_settings().CELERY_BROKER_URL,
    backend=get_settings().CELERY_RESULT_BACKEND,
    include=["app.services.tasks_manager"],  # Include tasks module
)


# PYTHONPATH=$(pwd) celery -A app.core.celery worker --loglevel=INFO  # This explicitly tells Python to include the current directory ($(pwd)) in its module search path.
# --concurrency = 8 <= cpu cores (better) # The concurrency options allows you to specify the number of worker processes or threads that should run conccurently to process the tasks. https://youtu.be/kRRkJx1-mpA?si=JJ8hqXyH-CP46FGr
