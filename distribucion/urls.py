from django.urls import path
from . import views, api_views

app_name = 'distribucion'

urlpatterns = [
    # Clientes
    path('clientes/', views.ClienteListView.as_view(), name='cliente_list'),
    path('clientes/nuevo/', views.ClienteCreateView.as_view(), name='cliente_create'),
    path('clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_update'),

    # Planillas (admin)
    path('planillas/', views.PlanillaListView.as_view(), name='planilla_list'),
    path('planillas/<int:pk>/', views.PlanillaDetailView.as_view(), name='planilla_detail'),
    path('planillas/<int:pk>/validar/', views.PlanillaValidarView.as_view(), name='planilla_validar'),

    # Vista de ruta (distribuidor)
    path('ruta/', views.PlanillaRutaListView.as_view(), name='ruta'),
    path('ruta/<int:pk>/', views.PlanillaRutaView.as_view(), name='ruta_planilla'),

    # API REST (sync híbrido)
    path('api/planilla-activa/', api_views.PlanillaActivaAPIView.as_view(), name='api_planilla_activa'),
    path('api/entregas/', api_views.EntregaCreateAPIView.as_view(), name='api_entrega_create'),
    path('api/averias/', api_views.AveriaCreateAPIView.as_view(), name='api_averia_create'),
    path('api/clientes/', api_views.ClienteListAPIView.as_view(), name='api_clientes'),
    path('api/productos/', api_views.ProductoListAPIView.as_view(), name='api_productos'),
]
