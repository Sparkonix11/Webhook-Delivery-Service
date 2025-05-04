import os
import logging
from app.workers.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# This script serves as an entry point for the celery worker
# It can be used to start a worker with: python worker.py
if __name__ == "__main__":
    # Start the worker
    celery_app.worker_main(
        argv=[
            'worker',
            '--loglevel=info',
            '--concurrency=4',
            '-Q',
            'webhooks,maintenance',  # Listen to both queues
        ]
    )