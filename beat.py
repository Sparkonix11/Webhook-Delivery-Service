import logging
from app.workers.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# This script serves as an entry point for the celery beat scheduler
# It can be used to start the beat scheduler with: python beat.py
if __name__ == "__main__":
    # Start the beat scheduler
    celery_app.start(
        argv=[
            'beat',
            '--loglevel=info',
        ]
    )