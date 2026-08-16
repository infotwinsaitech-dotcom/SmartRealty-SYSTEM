web: gunicorn realestate_crm.wsgi:application --workers 3 --threads 2 --timeout 60 --max-requests 1000 --max-requests-jitter 100
worker: celery -A realestate_crm worker --loglevel=info --concurrency=2
beat: celery -A realestate_crm beat --loglevel=info
release: python manage.py migrate --noinput