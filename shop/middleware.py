from .utils.audit import set_current_user, clear_current_user


class CurrentUserMiddleware:
    """
    Her istek başında request.user'ı thread-local'a koyar; response'ta temizler.
    Sinyaller bu sayede changed_by'ı otomatik görebilir.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            set_current_user(getattr(request, "user", None))
            return self.get_response(request)
        finally:
            clear_current_user()