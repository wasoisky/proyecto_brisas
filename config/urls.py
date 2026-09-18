"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from usuarios.mixins import INICIO_POR_ROL


class LoginConRolView(auth_views.LoginView):
    template_name = 'registration/login.html'

    def get_success_url(self):
        if url := self.get_redirect_url():
            return url
        rol = getattr(self.request.user, 'rol', None)
        return INICIO_POR_ROL.get(rol, '/reportes/')


def home_redirect(request):
    if request.user.is_authenticated:
        rol = getattr(request.user, 'rol', None)
        return redirect(INICIO_POR_ROL.get(rol, '/reportes/'))
    return redirect('login')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', LoginConRolView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', home_redirect, name='home'),
    path('produccion/', include('produccion.urls', namespace='produccion')),
    path('activos/', include('activos.urls', namespace='activos')),
    path('distribucion/', include('distribucion.urls', namespace='distribucion')),
    path('reportes/', include('reportes.urls', namespace='reportes')),
    path('usuarios/', include('usuarios.urls', namespace='usuarios')),
]
