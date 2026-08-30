from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('', views.ReportesDashboardView.as_view(), name='dashboard'),
    path('ventas/', views.VentasConsolidadasView.as_view(), name='ventas'),
    path('ventas/exportar/', views.ExportarVentasExcelView.as_view(), name='ventas_excel'),
    path('ventas/pdf/', views.ExportarVentasPDFView.as_view(), name='ventas_pdf'),
    path('descuadres/', views.DescuadreListView.as_view(), name='descuadres'),
    path('descuadres/nuevo/', views.DescuadreCreateView.as_view(), name='descuadre_create'),
    path('descuadres/<int:pk>/resolver/', views.DescuadreResolverView.as_view(), name='descuadre_resolver'),
    path('creditos/', views.CreditosPendientesView.as_view(), name='creditos'),
    path('creditos/<int:pk>/pagar/', views.CreditoPagarView.as_view(), name='credito_pagar'),
]
