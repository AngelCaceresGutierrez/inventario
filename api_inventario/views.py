from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import *
from django.db.models import Q, F
import random
import string
# Create your views here.

@api_view(['GET'])
def traer_usuarios(request):
    usuarios = Usuarios.objects.values('usu_id', 'usu_rut', 'usu_nombre')
    return Response(list(usuarios))


@api_view(['POST'])
def iniciar_sesion(request):
    usu_rut = request.data.get('usu_rut')
    usu_clave = request.data.get('usu_clave')
    
    try:
        usuario = Usuarios.objects.get(usu_rut=usu_rut, usu_clave=usu_clave)
        return Response({'message': 'Inicio de sesión exitoso', 'usuario_id': usuario.usu_id},status=200)
    
    except Usuarios.DoesNotExist:
        return Response({'message': 'Credenciales incorrectas'}, status=400)


@api_view(['GET'])
def listar_productos(request):
    busqueda = request.GET.get('buscar')
    
    if busqueda:
        productos = Productos.objects.filter(Q(pro_codigo=busqueda) | Q(pro_nombre__icontains=busqueda), pro_ubicacion=1).values('pro_nombre', 'pro_precio', 'pro_precio_oferta', tipo = F('pro_tipo__tip_id'), ubicacion=F('pro_ubicacion__ubi_id'), codigo=F('pro_codigo'), cantidad=F('pro_cantidad'))

    return Response({'productos': productos})


@api_view(['GET'])
def traer_categorias(request):
    ubicacion = Ubicacion.objects.values('ubi_id', 'ubi_nombre')
    dueno = Dueno.objects.values('due_id', 'due_nombre')
    tipo = Tipo.objects.values('tip_id', 'tip_nombre')
    return Response({'ubicacion': ubicacion, 'dueno':dueno, 'tipo':tipo})


@api_view(['POST'])
def crear_producto(request):
    def generar_codigo():
        return ''.join(random.choices(string.digits, k=8))
    
    def verificar_codigo_unico():
        """Genera un código único que no exista en la base de datos"""
        while True:
            nuevo_codigo = generar_codigo()
            if not Productos.objects.filter(pro_codigo=nuevo_codigo).exists():
                return nuevo_codigo

    nombre = request.data.get('nombre')
    cantidad = request.data.get('cantidad')
    codigo = request.data.get('codigo')
    precio = request.data.get('precio')
    precio_oferta = request.data.get('precio_oferta')
    tipo = request.data.get('tipo')
    ubicacion = request.data.get('ubicacion')
    dueno = request.data.get('dueno')

    # Generar código único si no se proporciona o si ya existe
    if codigo is None or codigo == "" or Productos.objects.filter(pro_codigo=codigo).exists():
        codigo = verificar_codigo_unico()
        print(f"Código generado automáticamente: {codigo}")
        
    try:
        producto = Productos.objects.create(
            pro_nombre=nombre,
            pro_cantidad=cantidad,
            pro_codigo=codigo,
            pro_precio=precio,
            pro_precio_oferta=precio_oferta,
            pro_tipo_id=tipo,
            pro_ubicacion_id=ubicacion,
            pro_dueno_id=dueno,
            pro_estado=1
        )
        
        return Response({
            'message': 'Producto creado exitosamente',
            'producto': {
                'id': producto.pro_id,
                'nombre': producto.pro_nombre,
                'codigo': producto.pro_codigo,
                'cantidad': producto.pro_cantidad,
                'precio': producto.pro_precio
            }
        }, status=200)
        
    except Exception as e:
        return Response({'error': f'Error al crear producto: {str(e)}'}, status=500)
    