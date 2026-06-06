from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver


def _get_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _user_agent(request):
    return request.META.get('HTTP_USER_AGENT', '')[:300]


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    from .models import RegistroAcceso
    RegistroAcceso.objects.create(
        usuario=user,
        username_intento=user.username,
        accion=RegistroAcceso.Accion.LOGIN_OK,
        ip=_get_ip(request),
        user_agent=_user_agent(request),
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    from .models import RegistroAcceso
    if user and user.is_authenticated:
        RegistroAcceso.objects.create(
            usuario=user,
            username_intento=user.username,
            accion=RegistroAcceso.Accion.LOGOUT,
            ip=_get_ip(request),
            user_agent=_user_agent(request),
        )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    from .models import RegistroAcceso
    RegistroAcceso.objects.create(
        usuario=None,
        username_intento=credentials.get('username', '')[:150],
        accion=RegistroAcceso.Accion.LOGIN_FALLIDO,
        ip=_get_ip(request),
        user_agent=_user_agent(request),
    )
