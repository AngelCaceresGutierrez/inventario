from django.urls import path
from . import views

urlpatterns = [
    path('traer_usuarios/', views.traer_usuarios, name='traer_usuarios'),
    path('iniciar_sesion/', views.iniciar_sesion, name='iniciar_sesion'),
    path('listar_productos/', views.listar_productos, name='listar_productos'),
]