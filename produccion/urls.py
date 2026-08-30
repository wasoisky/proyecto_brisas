from django.urls import path
from . import views

app_name = 'produccion'

urlpatterns = [
    # Productos
    path('productos/', views.ProductoListView.as_view(), name='producto_list'),
    path('productos/nuevo/', views.ProductoCreateView.as_view(), name='producto_create'),
    path('productos/<int:pk>/editar/', views.ProductoUpdateView.as_view(), name='producto_update'),
    path('productos/<int:pk>/toggle/', views.ProductoToggleActivoView.as_view(), name='producto_toggle'),

    # Insumos
    path('insumos/', views.InsumoListView.as_view(), name='insumo_list'),
    path('insumos/nuevo/', views.InsumoCreateView.as_view(), name='insumo_create'),
    path('insumos/<int:pk>/editar/', views.InsumoUpdateView.as_view(), name='insumo_update'),
    path('insumos/<int:pk>/toggle/', views.InsumoToggleActivoView.as_view(), name='insumo_toggle'),

    # Registros de producción
    path('registro/', views.ProduccionListView.as_view(), name='produccion_list'),
    path('registro/nuevo/', views.ProduccionCreateView.as_view(), name='produccion_create'),
    path('registro/<int:pk>/', views.ProduccionDetailView.as_view(), name='produccion_detail'),

    # Compras de insumos
    path('compras/', views.CompraInsumoListView.as_view(), name='compra_list'),
    path('compras/nueva/', views.CompraInsumoCreateView.as_view(), name='compra_create'),

    # Regalías (producto entregado sin cobro)
    path('regalias/', views.RegaliaListView.as_view(), name='regalia_list'),
    path('regalias/nueva/', views.RegaliaCreateView.as_view(), name='regalia_create'),

    # Recetas de productos
    path('recetas/', views.RecetaListView.as_view(), name='receta_list'),
    path('recetas/<int:pk>/editar/', views.RecetaUpdateView.as_view(), name='receta_update'),
    path('api/receta/<int:producto_id>/', views.receta_api, name='receta_api'),

    # Kardex de insumo
    path('insumos/<int:pk>/kardex/', views.InsumoKardexView.as_view(), name='insumo_kardex'),
]