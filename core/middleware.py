import logging
import time
from django.http import JsonResponse

logger = logging.getLogger("core")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - start_time

        if duration > 1.0:
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.path} took {duration:.2f}s "
                f"User: {request.user if request.user.is_authenticated else 'Anonymous'}"
            )

        # BUG FIX: per-request logging changed INFO -> DEBUG.
        # At 1000+ users/day this was writing a log line for EVERY request,
        # which floods log storage/IO and can hit platform log-volume limits.
        # Slow requests (>1s) still get a WARNING above so problems are visible.
        logger.debug(
            f"{request.method} {request.path} - {response.status_code} - {duration:.3f}s"
        )
        return response


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response