from django.http import JsonResponse
from django.db import connection
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)

def healthz(request):
    """Health check endpoint for monitoring and load balancers."""
    try:
        # Test database connection
        connection.ensure_connection()
        # If we get here, database is accessible
        return JsonResponse({"status": "ok"}, status=200)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


def ratelimited(request, exception=None):
    """
    django-ratelimit için özelleştirilmiş yanıt.
    429 + Türkçe mesaj ve örnek bir Retry-After başlığı döndürür.
    """
    payload = {
        "status": "too_many_requests",
        "message": "Çok fazla istek gönderdiniz. Lütfen kısa bir süre sonra tekrar deneyin."
    }
    resp = JsonResponse(payload, status=429)
    # Basit, sabit bir bekleme süresi. İstersen ayarlardan okunacak hale getirebiliriz.
    resp["Retry-After"] = "60"
    return resp