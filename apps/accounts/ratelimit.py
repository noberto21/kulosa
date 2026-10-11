"""Small fixed-window rate limiter backed by Django's cache.

The default cache is per-process memory, which is fine for development. In
production configure a shared cache (Redis/Memcached) in CACHES so the limit
holds across workers. The client key is REMOTE_ADDR only; X-Forwarded-For is
not trusted because clients can spoof it. If you deploy behind a proxy,
make the proxy set REMOTE_ADDR (e.g. gunicorn --forwarded-allow-ips).
"""
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def rate_limit(scope, limit, window=300, methods=("POST",)):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method in methods:
                key = f"rl:{scope}:{request.META.get('REMOTE_ADDR', 'unknown')}"
                cache.add(key, 0, timeout=window)
                try:
                    count = cache.incr(key)
                except ValueError:  # key expired between add and incr
                    cache.set(key, 1, timeout=window)
                    count = 1
                if count > limit:
                    response = HttpResponse(
                        "Too many attempts. Please wait a few minutes and try again.",
                        status=429, content_type="text/plain",
                    )
                    response["Retry-After"] = str(window)
                    return response
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
