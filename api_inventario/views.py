from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import *
from django.db.models import Q, F
import random
import string
from datetime import datetime
import time
import requests

# Create your views here.

@api_view(['GET'])
def estoy_vivo(request):
    productos = Productos.objects.filter(pro_tipo_id = 1).values('pro_id')
    estoy_vivo_func()
    return Response(list(productos))

def estoy_vivo_func():
    time.sleep(60*8)
    try:
        response = requests.get('https://inventario-mzod.onrender.com/api/estoy_vivo/')
        print(f"Request completada. Status: {response.status_code}")
    except Exception as e:
        print(f"Error en la request: {e}")
    
    return



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
def productos_por_tipo(request):
    tipo = request.GET.get('tipo')
    productos = Productos.objects.filter(pro_tipo_id = int(tipo)).values('pro_id', 'pro_nombre','pro_precio','pro_precio_oferta').order_by('pro_nombre')
    return Response({'productos': list(productos)})

@api_view(['POST'])
def crear_venta(request):
    arrProductos = request.data.get('arr')
    print(arrProductos)
    monto_total = 0
    productos_vendidos = ''
    # Recorrer el array de productos
    for index, arr in enumerate(arrProductos):
        # Sumar los subtotales
        monto_total += arr['pro_subtotal']
        
        # Concatenar productos vendidos
        producto_actual = str(arr['pro_id']) + '_' + str(arr['pro_cantidad'])
        
        # Si es el último elemento, no agregar punto y coma
        if index == len(arrProductos) - 1:
            productos_vendidos += producto_actual
        else:
            # Si no es el último, agregar punto y coma
            productos_vendidos += producto_actual + ';'
    
    print(f"Monto total: {monto_total}")
    print(f"Productos vendidos: {productos_vendidos}")

    # Crear la venta en la base de datos
    try:
        Ventas.objects.create(
            ven_monto_total=monto_total,
            ven_productos=productos_vendidos,
            ven_fecha_registro=datetime.now()
        )
        
        return Response({
            'message': 'Venta creada exitosamente',
        }, status=200)
        
    except Exception as e:
        return Response({'error': f'Error al crear venta: {str(e)}'}, status=500)



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
                cantidad_vendida = int(ids[1])
                precio_unitario = prod['pro_precio']
                precio_oferta = prod['pro_precio_oferta']
                
                # Calcular el precio total con ofertas
                def calcular_precio_con_oferta(cantidad, precio_normal, precio_oferta_str):
                    if precio_oferta_str and 'x' in precio_oferta_str:
                        try:
                            partes = precio_oferta_str.split('x')
                            cantidad_oferta = int(partes[0])
                            precio_oferta_total = int(partes[1])
                            
                            # Calcular grupos de oferta y productos restantes
                            grupos_oferta = cantidad // cantidad_oferta
                            productos_restantes = cantidad % cantidad_oferta
                            
                            # Precio total = (grupos × precio_oferta) + (restantes × precio_normal)
                            precio_total = (grupos_oferta * precio_oferta_total) + (productos_restantes * precio_normal)
                            return precio_total
                        except (ValueError, IndexError):
                            # Si hay error en el formato, usar precio normal
                            return precio_normal * cantidad
                    else:
                        # No tiene oferta, usar precio normal
                        return precio_normal * cantidad

                precio_calculado = calcular_precio_con_oferta(cantidad_vendida, precio_unitario, precio_oferta)

                arr_productos.append({
                    'cantidad': cantidad_vendida, 
                    'producto': prod['pro_nombre'],
                    'precio': precio_unitario,
                    'precio_total': precio_calculado
                })

                # Distribuir por tipo de producto
                if prod['pro_tipo_id'] == 1:  # Ropa
                    pro_ropa += precio_calculado
                elif prod['pro_tipo_id'] == 2:  # Paquetería
                    pro_paqueteria += precio_calculado
                elif prod['pro_tipo_id'] == 3:  # Útiles escolares
                    pro_utiles += precio_calculado

                # Distribuir por dueño
                if prod['pro_dueno_id'] == 1:  # Mireya
                    pro_mireya += precio_calculado
                elif prod['pro_dueno_id'] == 2:  # Ivan
                    pro_ivan += precio_calculado
                elif prod['pro_dueno_id'] == 3:  # Paulina
                    pro_paulina += precio_calculado

    respuesta = {
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
    

