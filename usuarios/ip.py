import ipaddress

from django.conf import settings


def _es_ip(valor):
    try:
        ipaddress.ip_address(valor)
    except ValueError:
        return False
    return True


def obtener_ip_cliente(request):
    """IP del visitante detrás de los proxies de confianza.

    Cada proxy añade al final de X-Forwarded-For la IP desde la que recibió la
    petición, así que solo las últimas ``TRUSTED_PROXY_COUNT`` entradas las
    pusieron nuestros proxies; lo que el cliente antepone queda a la izquierda
    y se ignora. El visitante es la entrada que ese número de proxies dejó
    a la derecha. Si la cadena no cuadra (más corta de lo esperado o con
    basura) se usa REMOTE_ADDR, que no se puede falsear.
    """
    remote_addr = request.META.get('REMOTE_ADDR')
    proxies = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    cadena = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if proxies < 1 or not cadena:
        return remote_addr
    entradas = [e.strip() for e in cadena.split(',')]
    if len(entradas) < proxies:
        return remote_addr
    candidata = entradas[-proxies]
    return candidata if _es_ip(candidata) else remote_addr
