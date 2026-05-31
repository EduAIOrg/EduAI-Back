#!/bin/bash

echo "Starting EduAI Celery Worker..."

celery \
  -A app.celery_app.celery_app \
  worker \
  --loglevel=info \
  --pool=solo