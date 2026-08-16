#!/bin/bash
set -e
echo "🚀 SmartRealty Build Started"
pip install -r requirements.txt
echo "🗄️ Running migrations..."
python manage.py migrate --no-input
echo "💾 Cache table..."
python manage.py createcachetable --verbosity=0 || true
echo "🎨 Static files..."
python manage.py collectstatic --no-input --clear
echo "✅ Checks..."
python manage.py check --deploy || true
echo "🔍 Cache verify..."
python -c "
import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate_crm.settings')
import django; django.setup()
from django.core.cache import cache
try:
    cache.set('_build', 'ok', 10)
    print('✅ Cache OK')
except Exception as e:
    print(f'⚠️ Cache: {e}')
"
echo "🎉 Build complete!"