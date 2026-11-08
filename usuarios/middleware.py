from .auditoria import fijar_request, soltar_request


class AuditoriaMiddleware:
    """Deja la petición disponible para que la bitácora sepa quién hizo cada operación."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = fijar_request(request)
        try:
            return self.get_response(request)
        finally:
            soltar_request(token)
