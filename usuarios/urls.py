from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('', views.UsuarioListView.as_view(), name='lista'),
    path('nuevo/', views.UsuarioCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='editar'),
    path('<int:pk>/password/', views.UsuarioSetPasswordView.as_view(), name='password'),
    path('<int:pk>/toggle/', views.UsuarioToggleActivoView.as_view(), name='toggle'),
    path('accesos/', views.RegistroAccesoListView.as_view(), name='accesos'),
    path('backups/', views.BackupListView.as_view(), name='backups'),
    path('backups/generar/', views.BackupGenerarView.as_view(), name='backups_generar'),
    path('backups/<str:nombre>/descargar/', views.BackupDescargarView.as_view(), name='backups_descargar'),
]
