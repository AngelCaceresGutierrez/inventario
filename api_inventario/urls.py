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
    path('editar_producto/', views.editar_producto, name='editar_producto'),

    #Mantener vivo el servidor
    path('estoy_vivo/', views.estoy_vivo, name='estoy_vivo'),

    #Venta libre + lectura de nota por foto
    path('crear_venta_libre/', views.crear_venta_libre, name='crear_venta_libre'),
    path('guardar_correccion/', views.guardar_correccion, name='guardar_correccion'),
    path('leer_nota/', views.leer_nota, name='leer_nota'),

    #Contador informativo del free tier de Gemini
    path('uso_gemini/', views.uso_gemini, name='uso_gemini'),

]