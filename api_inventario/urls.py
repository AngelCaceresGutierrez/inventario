from django.urls import path
from . import views

urlpatterns = [
    path('traer_usuarios/', views.traer_usuarios, name='traer_usuarios'),
    path('iniciar_sesion/', views.iniciar_sesion, name='iniciar_sesion'),
    path('listar_productos/', views.listar_productos, name='listar_productos'),
    path('productos_por_tipo/', views.productos_por_tipo, name='productos_por_tipo'),
    path('crear_venta/', views.crear_venta, name='crear_venta'),

    path('traer_categorias/', views.traer_categorias, name='traer_categorias'),
    path('crear_producto/', views.crear_producto, name='crear_producto'),
    path('totales_vendidos_por_dia/', views.totales_vendidos_por_dia, name='totales_vendidos_por_dia'),

]