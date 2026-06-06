from django.urls import path
from . import views

app_name = 'activos'

urlpatterns = [
    path('', views.ActivosDashboardView.as_view(), name='dashboard'),
    path('movimientos/', views.MovimientoListView.as_view(), name='movimiento_list'),
    path('movimientos/nuevo/', views.MovimientoCreateView.as_view(), name='movimiento_create'),
    path('movimientos/<int:pk>/', views.MovimientoDetailView.as_view(), name='movimiento_detail'),
]
