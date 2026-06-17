# core/views_health.py
# ====================

from django.http import JsonResponse
from django.core.cache import cache
from django.db import connection
import time


def health_check(request):
    """
    Production health check endpoint
    URL: /health/
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
    
    # 3. Memory usage (basic)
    import psutil
    process = psutil.Process()
    status['checks']['memory_mb'] = round(process.memory_info().rss / 1024 / 1024, 2)
    
    status_code = 200 if status['status'] == 'healthy' else 503
    return JsonResponse(status, status=status_code)


def cache_status(request):
    """
    Detailed cache status for debugging
    URL: /health/cache/ (admin only recommended)
    """
    from django.core.cache import caches
    from django.db import connection
    
    cache_info = {}
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as total_entries,
                       COUNT(CASE WHEN expires > NOW() THEN 1 END) as active_entries
                FROM django_cache_table
            """)
            row = cursor.fetchone()
            cache_info['total_entries'] = row[0]
            cache_info['active_entries'] = row[1]
    except Exception as e:
        cache_info['error'] = str(e)
    
    # Test write/read speed
    import time
    start = time.time()
    cache.set('_speed_test', 'x' * 1000, 10)
    write_time = (time.time() - start) * 1000
    
    start = time.time()
    cache.get('_speed_test')
    read_time = (time.time() - start) * 1000
    
    return JsonResponse({
        'cache_table': cache_info,
        'performance_ms': {
            'write': round(write_time, 2),
            'read': round(read_time, 2)
        },
        'backend': str(cache._cache.__class__.__name__)
    })