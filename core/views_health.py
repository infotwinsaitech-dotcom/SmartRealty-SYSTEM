# core/views_health.py — Production Health Check

from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection
import time


def health_check(request):
    """
    Production health check endpoint
    URL: /health/
    Render isko use karta hai server ko monitor karne ke liye
    """
    status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'checks': {}
    }

    # 1. Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        status['checks']['database'] = 'ok'
    except Exception as e:
        status['checks']['database'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'

    # 2. Cache check
    try:
        cache.set('_health', 'ok', 10)
        if cache.get('_health') == 'ok':
            status['checks']['cache'] = 'ok'
        else:
            status['checks']['cache'] = 'read failed'
            status['status'] = 'unhealthy'
    except Exception as e:
        status['checks']['cache'] = f'error: {str(e)}'
        status['status'] = 'unhealthy'

    # 3. Memory check — BUG FIX: psutil optional hai, requirements mein nahi tha
    try:
        import psutil
        process = psutil.Process()
        status['checks']['memory_mb'] = round(process.memory_info().rss / 1024 / 1024, 2)
    except ImportError:
        status['checks']['memory_mb'] = 'psutil not installed'
    except Exception:
        status['checks']['memory_mb'] = 'unavailable'

    status_code = 200 if status['status'] == 'healthy' else 503
    return JsonResponse(status, status=status_code)


def cache_status(request):
    """
    Cache debug endpoint — /health/cache/
    """
    from django.core.cache import cache

    cache_info = {}

    # Test write/read speed
    start = time.time()
    cache.set('_speed_test', 'x' * 1000, 10)
    write_time = (time.time() - start) * 1000

    start = time.time()
    cache.get('_speed_test')
    read_time = (time.time() - start) * 1000

    return JsonResponse({
        'performance_ms': {
            'write': round(write_time, 2),
            'read': round(read_time, 2)
        },
        'backend': str(type(cache).__name__)
    })
