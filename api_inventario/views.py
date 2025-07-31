from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import *
from django.db.models import Q, F
import random
import string
from datetime import datetime

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


@api_view(['GET'])
def totales_vendidos_por_dia(request):
    hoy = request.GET.get('fecha')
    respuesta = []
    
    pro_mireya = 0
    pro_ivan = 0
    pro_paulina = 0

    pro_ropa = 0
    pro_paqueteria = 0
    pro_utiles = 0

    if not hoy:
        hoy = datetime.now().date()
    else: 
        hoy = datetime.strptime(hoy.strip(), '%Y-%m-%d')

    total_vendido = 0

    ventas = Ventas.objects.filter(ven_fecha_registro__date = hoy).values()
    arr_productos=[]
    for ven in ventas:
        total_vendido += ven['ven_monto_total']
        arr_prod = ven['ven_productos'].split(';')

        for arr in arr_prod:
            ids = arr.split('_')
            productos = Productos.objects.filter(pro_id=ids[0]).values()

            for prod in productos:

                arr_productos.append({
                    'cantidad': ids[1], 
                    'producto': prod['pro_nombre'],
                    'precio': prod['pro_precio']
                })

                # Ropa
                if prod['pro_tipo_id'] == 1:
                    cantidad_oferta= int(prod['pro_precio_oferta'].split('x')[0])
                    if cantidad_oferta ==  int(ids[1]):
                        precio_oferta= int(prod['pro_precio_oferta'].split('x')[1])
                        pro_ropa += precio_oferta
                    else:
                        pro_ropa += prod['pro_precio'] * int(ids[1])

                # Paqueteria
                elif prod['pro_tipo_id'] == 2:
                    cantidad_oferta= int(prod['pro_precio_oferta'].split('x')[0])
                    if cantidad_oferta ==  int(ids[1]):
                        precio_oferta= int(prod['pro_precio_oferta'].split('x')[1])
                        pro_paqueteria += precio_oferta
                    else:
                        pro_paqueteria += prod['pro_precio'] * int(ids[1])

                # Utiles escolares
                elif prod['pro_tipo_id'] == 3:
                    cantidad_oferta= int(prod['pro_precio_oferta'].split('x')[0])
                    if cantidad_oferta ==  int(ids[1]):
                        precio_oferta= int(prod['pro_precio_oferta'].split('x')[1])
                        pro_utiles += precio_oferta
                    else:
                        pro_utiles += prod['pro_precio'] * int(ids[1])

                # Mireya
                if prod['pro_dueno_id'] == 1:
                    cantidad_oferta= int(prod['pro_precio_oferta'].split('x')[0])
                    if cantidad_oferta ==  int(ids[1]):
                        precio_oferta= int(prod['pro_precio_oferta'].split('x')[1])
                        pro_mireya += precio_oferta
                    else:
                        pro_mireya += prod['pro_precio'] * int(ids[1])

                # Ivan
                elif prod['pro_dueno_id'] == 2:
                    cantidad_oferta= int(prod['pro_precio_oferta'].split('x')[0])
                    if cantidad_oferta ==  int(ids[1]):
                        precio_oferta= int(prod['pro_precio_oferta'].split('x')[1])
                        pro_ivan += precio_oferta
                    else:
                        pro_ivan += prod['pro_precio'] * int(ids[1])

                # Paulina
                elif prod['pro_dueno_id']== 3:
                    cantidad_oferta= int(prod['pro_precio_oferta'].split('x')[0])
                    if cantidad_oferta ==  int(ids[1]):
                        precio_oferta= int(prod['pro_precio_oferta'].split('x')[1])
                        pro_paulina += precio_oferta
                    else:
                        pro_paulina += prod['pro_precio'] * int(ids[1])        

    respuesta={
        'fecha': hoy.strftime("%d-%m-%Y"),
        'total_vendido': total_vendido,
        'vendido_mireya': pro_mireya,
        'vendido_ivan': pro_ivan,
        'vendido_paulina': pro_paulina,
        'vendido_ropa': pro_ropa,
        'vendido_paqueteria': pro_paqueteria,
        'vendido_utiles': pro_utiles,
        'productos': list(arr_productos)
    }

    return Response({'respuesta': respuesta})


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
        
    precio_oferta = precio_oferta.replace(" ", "")
    print(precio_oferta)
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
    