from django.shortcuts import render
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import *
from django.db.models import Q, F
from django.db import IntegrityError, transaction
import calendar
import difflib
import random
import string
import unicodedata
from datetime import datetime, timedelta
import time
import requests
import json
import traceback
import base64

# ---------------------------------------------------------------------------
# Lectura de nota por foto (Gemini) — constantes y helpers compartidos
# ---------------------------------------------------------------------------

def _detectar_formato_imagen(cabecera):
    """Formato real por magic bytes (el content_type declarado en el multipart
    no es confiable: Android envía fotos sin un content-type usable)."""
    if cabecera[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if cabecera[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return 'image/webp'
    return None
TAMANO_MAXIMO_IMAGEN = 5 * 1024 * 1024
VALOR_MAXIMO_INT4 = 2147483647  # Tope de las columnas INTEGER de Postgres

PROMPT_LECTURA_NOTA = (
    "Transcribe esta nota manuscrita de ventas de feria. Cada línea tiene el formato "
    "'nombre precio' (precio en pesos chilenos, número entero sin símbolos; puede decir "
    "'x' o '2x1500' para ofertas: en ese caso registra el valor total del pack en el "
    "campo valor). Nombres en minúscula tal como se leen. Si una línea no se entiende "
    "con confianza (ilegible, sin precio, ambigua) ponla en dudosos con el texto crudo "
    "tal como se ve. No inventes precios. Si la nota está vacía o es ilegible por "
    "completo, devuelve las listas vacías."
)

SCHEMA_LECTURA_NOTA = {
    "type": "OBJECT",
    "properties": {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nombre": {"type": "STRING"},
                    "valor": {"type": "INTEGER"},
                },
                "required": ["nombre", "valor"],
            },
        },
        "dudosos": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "texto_crudo": {"type": "STRING"},
                    "razon": {"type": "STRING"},
                },
                "required": ["texto_crudo"],
            },
        },
    },
    "required": ["items", "dudosos"],
}


def _texto_valido(texto):
    """String no vacío y <= 100 caracteres (convención VARCHAR(100) del esquema)."""
    return isinstance(texto, str) and 0 < len(texto.strip()) <= 100


def _entero_no_negativo(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def _respuesta_invalido(mensaje):
    return Response({'error': mensaje, 'codigo': 'PAYLOAD_INVALIDO'}, status=400)


def _uso_gemini_hoy():
    """Estado informativo del cupo diario de Gemini; sin fila de hoy → todo en 0."""
    fila = UsoGemini.objects.filter(ug_fecha=datetime.now().date()).first()
    lecturas = fila.ug_lecturas if fila else 0
    tokens = fila.ug_tokens if fila else 0
    limite = settings.GEMINI_RPD_LIMITE
    return {
        'lecturas_hoy': lecturas,
        'tokens_hoy': tokens,
        'limite_rpd': limite,
        'restantes': max(0, limite - lecturas),
    }


def _registrar_uso_gemini(tokens):
    """Acumula 1 lectura + tokens de hoy (upsert) y devuelve el estado del cupo."""
    hoy = datetime.now().date()
    try:
        # Primer día (o primera fila): insert directo
        UsoGemini.objects.create(ug_fecha=hoy, ug_lecturas=1, ug_tokens=tokens)
    except IntegrityError:
        # La fila de hoy ya existe (carrera entre requests): acumulación atómica en SQL
        UsoGemini.objects.filter(ug_fecha=hoy).update(
            ug_lecturas=F('ug_lecturas') + 1,
            ug_tokens=F('ug_tokens') + tokens,
        )
    return _uso_gemini_hoy()

# Create your views here.

def estoy_vivo_func():
    time.sleep(60*8)
    try:
        response = requests.get('https://inventario-mzod.onrender.com/api/estoy_vivo/')
        print(f"Request completada. Status: {response.status_code}")
    except Exception as e:
        print(f"Error en la request: {e}")
    
    return



@api_view(['GET'])
def estoy_vivo(request):
    productos = Productos.objects.filter(pro_tipo_id = 1).values('pro_id')
    estoy_vivo_func()
    return Response(list(productos))



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
        productos = Productos.objects.filter(Q(pro_codigo=busqueda) | Q(pro_nombre__icontains=busqueda), pro_ubicacion=1).values('pro_id','pro_nombre', 'pro_precio', 'pro_precio_oferta', tipo = F('pro_tipo__tip_id'), ubicacion=F('pro_ubicacion__ubi_id'), codigo=F('pro_codigo'), cantidad=F('pro_cantidad'),dueno=F('pro_dueno')).order_by('pro_nombre')

    return Response({'productos': productos})


@api_view(['GET'])
def traer_categorias(request):
    ubicacion = Ubicacion.objects.values('ubi_id', 'ubi_nombre')
    dueno = Dueno.objects.exclude(due_estado=False).values('due_id', 'due_nombre') # oculta duenos desactivados
    tipo = Tipo.objects.values('tip_id', 'tip_nombre')
    return Response({'ubicacion': ubicacion, 'dueno':dueno, 'tipo':tipo})

@api_view(['GET'])
def productos_por_tipo(request):
    tipo = request.GET.get('tipo')
    productos = Productos.objects.values('pro_id', 'pro_nombre','pro_precio','pro_precio_oferta','pro_codigo').order_by('pro_nombre')
    
    if tipo:
        productos = productos.filter(pro_tipo_id = int(tipo))
   
    return Response({'productos': list(productos)})

@api_view(['POST'])
def crear_venta(request):
    arrProductos = request.data.get('arr')
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

    # Crear la venta en la base de datos
    try:
        Ventas.objects.create(
            ven_monto_total=monto_total,
            ven_productos=productos_vendidos,
            ven_fecha_registro=datetime.now(),
            ven_puesto = arr['puesto']
        )
        
        return Response({
            'message': 'Venta creada exitosamente',
        }, status=200)
        
    except Exception as e:
        return Response({'error': f'Error al crear venta: {str(e)}'}, status=500)


@api_view(['PATCH'])
def editar_producto(request):
    id = request.data.get('id')
    producto = request.data.get('prod')
    try:
        if isinstance(producto, str):
            producto = json.loads(producto)
        Productos.objects.filter(pro_id=id).update(**producto)
        return Response({
            'message': 'Producto editado exitosamente',
        }, status=200)
        
    except Exception as e:
        traceback.print_exc()
        return Response({'error': f'Error al editar producto: {str(e)}'}, status=500)


@api_view(['GET'])
def totales_vendidos_por_dia(request):
    hoy = request.GET.get('fecha')
    puesto = request.GET.get('puesto')
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

    # Filtro opcional por puesto (si no viene: comportamiento global de siempre)
    puesto_val = None
    if puesto is not None:
        try:
            puesto_val = int(puesto)
            if puesto_val <= 0:
                raise ValueError
        except ValueError:
            return _respuesta_invalido('Puesto inválido: debe ser un entero mayor a 0')

    total_vendido = 0

    ventas = Ventas.objects.filter(ven_fecha_registro__date = hoy)
    if puesto_val is not None:
        ventas = ventas.filter(ven_puesto = puesto_val)
    ventas = ventas.values()
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

    # Ventas libres del día (ítems sin vínculo al inventario): suman al total,
    # se listan en productos[] y se atribuyen al dueño de su puesto
    # (1 = Mireya, 2 = Ivan) — no son una categoría aparte.
    libres = VentasLibres.objects.filter(vl_fecha_registro__date = hoy)
    if puesto_val is not None:
        libres = libres.filter(vl_puesto = puesto_val)
    libres = list(libres.values('vl_nombre', 'vl_valor', 'vl_puesto'))

    total_vendido += sum(l['vl_valor'] for l in libres)

    for lib in libres:
        if lib['vl_puesto'] == 1:  # Mireya
            pro_mireya += lib['vl_valor']
        elif lib['vl_puesto'] == 2:  # Ivan
            pro_ivan += lib['vl_valor']

    for lib in libres:
        arr_productos.append({
            'cantidad': 1,
            'producto': lib['vl_nombre'],
            'precio': lib['vl_valor'],
            'precio_total': lib['vl_valor'],
        })

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


@api_view(['POST'])
def crear_venta_libre(request):
    """Venta libre: ítems {nombre, valor} sin vínculo al inventario, por puesto.
    Cada texto libre intenta asociarse a un producto (aprendizaje permanente):
    1) asociación ya guardada, 2) auto-match por similitud >= UMBRAL_MATCH
    (guarda asociación automática), 3) sin match → fila en pendientes."""
    puesto = request.data.get('puesto')
    items = request.data.get('items')

    if not _entero_no_negativo(puesto) or puesto <= 0:
        return _respuesta_invalido('Puesto requerido: entero mayor a 0')
    if not isinstance(items, list) or not (1 <= len(items) <= 50):
        return _respuesta_invalido('Items requeridos: lista de 1 a 50 ítems')

    # Whitelist: por ítem solo se leen nombre y valor; todo lo demás se ignora.
    for i, item in enumerate(items):
        nombre = item.get('nombre') if isinstance(item, dict) else None
        valor = item.get('valor') if isinstance(item, dict) else None
        if not _texto_valido(nombre):
            return _respuesta_invalido(f'Item inválido [{i}]: nombre requerido (texto, máximo 100 caracteres)')
        if not _entero_no_negativo(valor):
            return _respuesta_invalido(f'Item inválido [{i}]: valor requerido (entero >= 0)')
        if valor > VALOR_MAXIMO_INT4:
            return _respuesta_invalido(f'Item inválido [{i}]: valor fuera de rango (máximo {VALOR_MAXIMO_INT4})')

    try:
        # Fecha NAIVE igual que todo el proyecto (columnas TIMESTAMP sin tz,
        # datos históricos naive, hora local Chile UTC-3): NO usar timezone.now().
        ahora = datetime.now()
        auto = pendientes = 0
        # Todo o nada: una venta parcial se duplicaría cuando el cliente reintente.
        with transaction.atomic():
            for item in items:
                VentasLibres.objects.create(
                    vl_nombre=item['nombre'].strip(),
                    vl_valor=item['valor'],
                    vl_fecha_registro=ahora,
                    vl_puesto=puesto,
                )
                # Asociación texto→producto: información aparte, el nombre libre no cambia.
                normalizado = _normalizar_texto(item['nombre'])
                if AsociacionProducto.objects.filter(ap_texto__iexact=normalizado).exists():
                    continue  # ya aprendido, nada más que hacer
                match = _mejor_match_producto(item['nombre'])
                if match is not None:
                    AsociacionProducto.objects.update_or_create(
                        ap_texto=normalizado,
                        defaults={'ap_producto_id': match, 'ap_automatica': True, 'ap_fecha': ahora},
                    )
                    PendienteProducto.objects.filter(pp_texto__iexact=normalizado).delete()
                    auto += 1
                else:
                    fila, creado = PendienteProducto.objects.get_or_create(
                        pp_texto=normalizado, defaults={'pp_veces': 1, 'pp_fecha_ultimo': ahora},
                    )
                    if not creado:
                        PendienteProducto.objects.filter(pp_id=fila.pp_id).update(
                            pp_veces=F('pp_veces') + 1, pp_fecha_ultimo=ahora,
                        )
                    pendientes += 1
    except Exception:
        traceback.print_exc()
        return Response({'error': 'Error al crear venta libre', 'codigo': 'ERROR_BD'}, status=500)

    return Response({
        'message': 'Ventas libres creadas',
        'ventas_creadas': len(items),
        'asociaciones': {'auto': auto, 'pendientes': pendientes},
    }, status=200)


# ---------------------------------------------------------------------------
# Asociación de ventas libres a productos (aprendizaje texto→producto)
# ---------------------------------------------------------------------------

UMBRAL_MATCH = 0.9


def _normalizar_texto(s):
    """minúsculas, sin acentos (NFD), espacios colapsados y strip.
    El resultado es la clave canónica de asociaciones y pendientes."""
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return ' '.join(s.split())


def _mejor_match_producto(nombre):
    """Producto cuyo nombre normalizado es casi idéntico al texto (>= UMBRAL_MATCH),
    o None. Empate en el máximo o nada sobre el umbral → None (ambigüedad no adivina)."""
    objetivo = _normalizar_texto(nombre)
    mejor_id, mejor_score, empate = None, 0.0, False
    for pro_id, pro_nombre in Productos.objects.values_list('pro_id', 'pro_nombre'):
        score = difflib.SequenceMatcher(None, objetivo, _normalizar_texto(pro_nombre or '')).ratio()
        if score >= UMBRAL_MATCH:
            if score > mejor_score:
                mejor_id, mejor_score, empate = pro_id, score, False
            elif score == mejor_score and pro_id != mejor_id:
                empate = True
    return None if empate else mejor_id


@api_view(['GET'])
def listar_pendientes(request):
    """Textos de venta libre aún sin producto, más recientes primero."""
    filas = PendienteProducto.objects.order_by('-pp_fecha_ultimo').values('pp_texto', 'pp_veces', 'pp_fecha_ultimo')
    pendientes = [{
        'texto': f['pp_texto'],
        'veces': f['pp_veces'],
        'ultima': f['pp_fecha_ultimo'].strftime('%Y-%m-%d %H:%M'),
    } for f in filas]
    return Response({'pendientes': pendientes, 'total': len(pendientes)})


@api_view(['POST'])
def asociar_pendiente(request):
    """Asociación manual texto→producto: guarda el aprendizaje y borra el pendiente."""
    texto = request.data.get('texto')
    producto_id = request.data.get('producto_id')

    if not _texto_valido(texto):
        return _respuesta_invalido('Texto requerido: no vacío y máximo 100 caracteres')
    producto = Productos.objects.filter(pro_id=producto_id).first()
    if producto is None:
        return Response({'error': 'Producto no encontrado', 'codigo': 'PRODUCTO_INVALIDO'}, status=400)

    normalizado = _normalizar_texto(texto)
    try:
        # Upsert idempotente (mismo criterio que guardar_correccion): re-asociar
        # un texto ya aprendido actualiza el producto, no falla por UNIQUE.
        AsociacionProducto.objects.update_or_create(
            ap_texto=normalizado,
            defaults={'ap_producto_id': producto.pro_id, 'ap_automatica': False, 'ap_fecha': datetime.now()},
        )
        PendienteProducto.objects.filter(pp_texto__iexact=normalizado).delete()
    except Exception:
        traceback.print_exc()
        return Response({'error': 'Error al guardar asociación', 'codigo': 'ERROR_BD'}, status=500)

    return Response({'message': 'Asociacion guardada', 'texto': normalizado, 'producto': producto.pro_nombre}, status=200)


@api_view(['GET'])
def listar_asociaciones(request):
    """Auditoría del aprendizaje texto→producto, más recientes primero."""
    filas = AsociacionProducto.objects.order_by('-ap_fecha').values(
        'ap_texto', 'ap_producto_id', 'ap_producto__pro_nombre', 'ap_automatica', 'ap_fecha',
    )
    asociaciones = [{
        'texto': f['ap_texto'],
        'producto_id': f['ap_producto_id'],
        'producto_nombre': f['ap_producto__pro_nombre'],
        'automatica': f['ap_automatica'],
        'fecha': f['ap_fecha'].strftime('%Y-%m-%d %H:%M'),
    } for f in filas]
    return Response({'asociaciones': asociaciones, 'total': len(asociaciones)})


@api_view(['POST'])
def guardar_correccion(request):
    """Diccionario GLOBAL de correcciones de lectura: upsert idempotente por texto_crudo."""
    correcciones = request.data.get('correcciones')

    if not isinstance(correcciones, list) or not (1 <= len(correcciones) <= 20):
        return _respuesta_invalido('Correcciones requeridas: lista de 1 a 20 elementos')

    # Whitelist: por corrección solo texto_crudo, nombre y valor.
    for i, c in enumerate(correcciones):
        texto = c.get('texto_crudo') if isinstance(c, dict) else None
        nombre = c.get('nombre') if isinstance(c, dict) else None
        valor = c.get('valor') if isinstance(c, dict) else None
        if not _texto_valido(texto) or not _texto_valido(nombre):
            return _respuesta_invalido(f'Corrección inválida [{i}]: texto_crudo y nombre requeridos (texto, máximo 100 caracteres)')
        if not _entero_no_negativo(valor):
            return _respuesta_invalido(f'Corrección inválida [{i}]: valor requerido (entero >= 0)')

    try:
        for c in correcciones:
            # Upsert: corregir dos veces lo mismo actualiza, no duplica
            # (UNIQUE uq_correcciones_texto en BD).
            CorreccionesLectura.objects.update_or_create(
                cl_texto_crudo=c['texto_crudo'].strip(),
                defaults={
                    'cl_nombre_corregida': c['nombre'].strip(),
                    'cl_valor_corregido': c['valor'],
                    'cl_fecha_registro': datetime.now(),
                },
            )
    except Exception:
        traceback.print_exc()
        return Response({'error': 'Error al guardar correcciones', 'codigo': 'ERROR_BD'}, status=500)

    return Response({'message': 'Correcciones guardadas', 'correcciones_guardadas': len(correcciones)}, status=200)


@api_view(['POST'])
def leer_nota(request):
    """Lectura de nota manuscrita por foto: Gemini Flash + diccionario global aplicado."""
    imagen = request.FILES.get('imagen')

    if not imagen:
        return _respuesta_invalido('Imagen requerida (campo imagen del formulario)')
    cabecera = imagen.read(12)
    imagen.seek(0)
    formato = _detectar_formato_imagen(cabecera)
    if not formato:
        return _respuesta_invalido('Tipo de imagen no permitido (solo JPEG, PNG o WebP)')
    if imagen.size > TAMANO_MAXIMO_IMAGEN:
        return Response({'error': 'La imagen supera el máximo de 5 MB', 'codigo': 'IMAGEN_MUY_GRANDE'}, status=413)
    if not settings.GEMINI_API_KEY:
        return Response({'error': 'Lectura por foto no configurada en el servidor (falta GEMINI_API_KEY)', 'codigo': 'GEMINI_NO_CONFIGURADA'}, status=503)

    # Diccionario global de correcciones (se acota a las 100 más recientes por si crece)
    dicc = list(
        CorreccionesLectura.objects
        .order_by('-cl_fecha_registro')
        .values('cl_texto_crudo', 'cl_nombre_corregida', 'cl_valor_corregido')[:100]
    )

    prompt = PROMPT_LECTURA_NOTA
    if dicc:
        bloque_dicc = '\n'.join(
            f'- texto leído "{d["cl_texto_crudo"]}" → nombre correcto "{d["cl_nombre_corregida"]}", valor {d["cl_valor_corregido"]}'
            for d in dicc
        )
        prompt += (
            '\n\nDICCIONARIO DE CORRECCIONES YA CONOCIDAS. Si lo que lees coincide con '
            'el texto leído, usa la corrección indicada:\n' + bloque_dicc
        )

    # La imagen vive solo en memoria (base64); nunca a disco, BD ni logs.
    cuerpo = {
        'contents': [{
            'parts': [
                {'text': prompt},
                {'inline_data': {'mime_type': formato, 'data': base64.b64encode(imagen.read()).decode('ascii')}},
            ],
        }],
        'generationConfig': {
            'temperature': 0,
            'responseMimeType': 'application/json',
            'responseSchema': SCHEMA_LECTURA_NOTA,
            # Presupuesto completo: notas de feria con 50+ lineas
            # (el pensamiento del modelo consume este mismo budget y
            # truncaba el JSON a ~26 items).
            'maxOutputTokens': 65536,
            # OCR no necesita pensamiento: respuesta mas rapida y todo
            # el budget disponible para los items.
            'thinkingConfig': {'thinkingBudget': 0},
        },
    }

    try:
        respuesta_google = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent',
            headers={'x-goog-api-key': settings.GEMINI_API_KEY},
            json=cuerpo,
            timeout=120,
        )
    except requests.exceptions.Timeout:
        return Response({'error': 'La lectura tardó demasiado; reintenta o ingresa los ítems manualmente', 'codigo': 'GEMINI_TIMEOUT'}, status=502)
    except requests.exceptions.RequestException:
        traceback.print_exc()
        return Response({'error': 'No se pudo contactar el servicio de lectura; reintenta o ingresa manualmente', 'codigo': 'GEMINI_RECHAZO'}, status=502)

    if respuesta_google.status_code == 429:
        return Response({'error': 'Cuota gratuita de lectura agotada por hoy; ingresa los ítems manualmente', 'codigo': 'GEMINI_CUOTA_AGOTADA'}, status=502)
    if respuesta_google.status_code != 200:
        return Response({'error': f'El servicio de lectura rechazó la solicitud (HTTP {respuesta_google.status_code}); reintenta o ingresa manualmente', 'codigo': 'GEMINI_RECHAZO'}, status=502)

    try:
        body = respuesta_google.json()
        contenido = body['candidates'][0]['content']['parts'][0]['text']
        lectura = json.loads(contenido)
        items = lectura['items']
        dudosos = lectura['dudosos']
    except (ValueError, KeyError, IndexError, TypeError):
        traceback.print_exc()
        return Response({'error': 'La respuesta del servicio de lectura no se pudo interpretar; reintenta o ingresa manualmente', 'codigo': 'GEMINI_RESPUESTA_INVALIDA'}, status=502)

    # Post-proceso con el diccionario: garantía de que la corrección se aplica
    # 100% de las veces, independiente de si el modelo siguió el prompt.
    mapa = {d['cl_texto_crudo'].strip().lower(): d for d in dicc}

    items_finales = []
    for item in items:
        nombre = item.get('nombre')
        corr = mapa.get(str(nombre).strip().lower()) if nombre is not None else None
        if corr:
            items_finales.append({'nombre': corr['cl_nombre_corregida'], 'valor': corr['cl_valor_corregido']})
        else:
            items_finales.append({'nombre': nombre, 'valor': item.get('valor')})

    dudosos_restantes = []
    for dudoso in dudosos:
        corr = mapa.get(str(dudoso.get('texto_crudo')).strip().lower())
        if corr:
            items_finales.append({'nombre': corr['cl_nombre_corregida'], 'valor': corr['cl_valor_corregido']})
        else:
            dudosos_restantes.append(dudoso)

    # ponytail: un 200 con contenido ilegible no cuenta lectura aunque el cupo
    # sí se gastó; si algún día importa, registrar antes del try del parseo.
    tokens = (body.get('usageMetadata') or {}).get('totalTokenCount') or 0
    uso = _registrar_uso_gemini(tokens)

    return Response({'items': items_finales, 'dudosos': dudosos_restantes, 'uso': uso}, status=200)


@api_view(['GET'])
def uso_gemini(request):
    """Cupo diario gratuito de Gemini consumido hoy (informativo, nunca bloquea)."""
    try:
        return Response(_uso_gemini_hoy(), status=200)
    except Exception:
        traceback.print_exc()
        return Response({'error': 'Error al consultar el uso de Gemini', 'codigo': 'ERROR_BD'}, status=500)


# ---------------------------------------------------------------------------
# Resumen de gerencia (GET /api/resumen_gerencia/): serie de ventas por bucket
# (mes/semana/dia) con desglose por dueño, puesto y tipo. Solo lectura, sin
# filtro de puesto: la gerencia ve TODOS los puestos juntos.
# ---------------------------------------------------------------------------

# Mapeos por ID con el mismo criterio de totales_vendidos_por_dia, fijados por
# contrato con el frontend. Si algún día cambian dueños/tipos en BD, actualizar
# aquí (única fuente para este endpoint).
RESUMEN_DUENOS_POR_ID = {1: 'mireya', 2: 'ivan', 3: 'paulina'}
RESUMEN_TIPOS_POR_ID = {1: 'Ropa', 2: 'Paqueteria', 3: 'Utiles escolares'}
# Ventas libres: dueño = su puesto (1=Mireya, 2=Ivan); otros puestos solo total.
RESUMEN_DUENO_POR_PUESTO_LIBRE = {1: 'mireya', 2: 'ivan'}


def _precio_con_oferta(cantidad, precio_normal, precio_oferta_str):
    """Precio total de un producto vendido respetando ofertas '2x1000'.
    ponytail: duplicada de la copia local de totales_vendidos_por_dia porque
    ese endpoint no debe modificarse; si se extrae, esta se elimina."""
    if precio_oferta_str and 'x' in precio_oferta_str:
        try:
            partes = precio_oferta_str.split('x')
            cantidad_oferta = int(partes[0])
            precio_oferta_total = int(partes[1])

            grupos_oferta = cantidad // cantidad_oferta
            productos_restantes = cantidad % cantidad_oferta

            return (grupos_oferta * precio_oferta_total) + (productos_restantes * precio_normal)
        except (ValueError, IndexError):
            return precio_normal * cantidad
    return precio_normal * cantidad


def _clave_bucket(nivel, fecha_hora):
    """Clave de serie para un timestamp: hora '0'..'23' en nivel dia,
    fecha 'YYYY-MM-DD' en mes/semana."""
    if nivel == 'dia':
        return str(fecha_hora.hour)
    return fecha_hora.date().isoformat()


@api_view(['GET'])
def resumen_gerencia(request):
    """Ventas del periodo (ventas + ventas_libres) agrupadas en buckets por
    dueño. Una query por tabla, productos en un solo batch (sin N+1)."""
    nivel = request.GET.get('nivel', 'mes')
    if nivel not in ('mes', 'semana', 'dia'):
        return _respuesta_invalido('Nivel inválido: debe ser mes, semana o dia')

    fecha_param = request.GET.get('fecha')
    if fecha_param:
        try:
            fecha = datetime.strptime(fecha_param.strip(), '%Y-%m-%d').date()
        except ValueError:
            return _respuesta_invalido('Fecha inválida: formato esperado YYYY-MM-DD')
    else:
        # Criterio naive del proyecto (columnas TIMESTAMP sin tz): nunca timezone.now()
        fecha = datetime.now().date()

    # Rango [inicio, fin) naive + claves de bucket según nivel (todos los
    # buckets del periodo van en la serie, sin ventas = ceros).
    if nivel == 'dia':
        inicio = datetime.combine(fecha, datetime.min.time())
        fin = inicio + timedelta(days=1)
        claves_bucket = [str(hora) for hora in range(24)]
    elif nivel == 'semana':
        lunes = fecha - timedelta(days=fecha.weekday())
        inicio = datetime.combine(lunes, datetime.min.time())
        fin = inicio + timedelta(days=7)
        claves_bucket = [(inicio + timedelta(days=dia)).date().isoformat() for dia in range(7)]
    else:  # mes
        primer_dia = fecha.replace(day=1)
        inicio = datetime.combine(primer_dia, datetime.min.time())
        fin = inicio + timedelta(days=calendar.monthrange(fecha.year, fecha.month)[1])
        claves_bucket = [(inicio + timedelta(days=dia)).date().isoformat() for dia in range((fin - inicio).days)]

    desglose_bucket = {clave: {'mireya': 0, 'ivan': 0, 'paulina': 0} for clave in claves_bucket}
    por_dueno = {'mireya': 0, 'ivan': 0, 'paulina': 0}
    por_puesto = {}
    por_tipo = {}

    # --- Ventas viejas: dueño/tipo desde el serializado ven_productos ---
    ventas = list(Ventas.objects.filter(
        ven_fecha_registro__gte=inicio, ven_fecha_registro__lt=fin,
    ).values('ven_fecha_registro', 'ven_productos', 'ven_puesto'))

    ids_producto = {
        int(trozo.split('_')[0])
        for ven in ventas
        for trozo in ven['ven_productos'].split(';')
        if trozo.split('_')[0].isdigit()
    }
    mapa_productos = {p['pro_id']: p for p in Productos.objects.filter(
        pro_id__in=ids_producto,
    ).values('pro_id', 'pro_precio', 'pro_precio_oferta', 'pro_dueno_id', 'pro_tipo_id')}

    for ven in ventas:
        acumulador = desglose_bucket[_clave_bucket(nivel, ven['ven_fecha_registro'])]
        for trozo in ven['ven_productos'].split(';'):
            partes = trozo.split('_')
            # Trozo malformado o producto borrado: sin dueño/tipo conocido,
            # se ignora (mismo efecto que el patrón de la vista diaria)
            if len(partes) != 2 or not partes[0].isdigit() or not partes[1].isdigit():
                continue
            producto = mapa_productos.get(int(partes[0]))
            if producto is None:
                continue
            precio = _precio_con_oferta(int(partes[1]), producto['pro_precio'], producto['pro_precio_oferta'])

            dueno = RESUMEN_DUENOS_POR_ID.get(producto['pro_dueno_id'])
            if dueno:
                acumulador[dueno] += precio
                por_dueno[dueno] += precio
            tipo = RESUMEN_TIPOS_POR_ID.get(producto['pro_tipo_id'])
            if tipo:
                por_tipo[tipo] = por_tipo.get(tipo, 0) + precio
            if ven['ven_puesto'] is not None:
                clave_puesto = str(ven['ven_puesto'])
                por_puesto[clave_puesto] = por_puesto.get(clave_puesto, 0) + precio

    # --- Ventas libres: 100% al dueño de su puesto ---
    libres = list(VentasLibres.objects.filter(
        vl_fecha_registro__gte=inicio, vl_fecha_registro__lt=fin,
    ).values('vl_fecha_registro', 'vl_nombre', 'vl_valor', 'vl_puesto'))

    # Tipo resuelto al consultar: asociar un pendiente incluye sus ventas pasadas.
    nombres_normalizados = [_normalizar_texto(lib['vl_nombre']) for lib in libres]
    tipo_por_texto = dict(AsociacionProducto.objects.filter(
        ap_texto__in=set(nombres_normalizados),
    ).values_list('ap_texto', 'ap_producto__pro_tipo_id'))

    for lib, texto in zip(libres, nombres_normalizados):
        acumulador = desglose_bucket[_clave_bucket(nivel, lib['vl_fecha_registro'])]
        dueno = RESUMEN_DUENO_POR_PUESTO_LIBRE.get(lib['vl_puesto'])
        if dueno:
            acumulador[dueno] += lib['vl_valor']
            por_dueno[dueno] += lib['vl_valor']
        # El monto sale de la venta (vl_valor), nunca del precio del producto.
        tipo = RESUMEN_TIPOS_POR_ID.get(tipo_por_texto.get(texto))
        if tipo:
            por_tipo[tipo] = por_tipo.get(tipo, 0) + lib['vl_valor']
        clave_puesto = str(lib['vl_puesto'])
        por_puesto[clave_puesto] = por_puesto.get(clave_puesto, 0) + lib['vl_valor']

    serie = []
    for clave in claves_bucket:
        desglose = desglose_bucket[clave]
        serie.append({
            'bucket': clave,
            'total': desglose['mireya'] + desglose['ivan'] + desglose['paulina'],
            'mireya': desglose['mireya'],
            'ivan': desglose['ivan'],
            'paulina': desglose['paulina'],
        })

    return Response({
        'nivel': nivel,
        'fecha': fecha.isoformat(),
        'serie': serie,
        'total': sum(entrada['total'] for entrada in serie),
        'por_dueno': por_dueno,
        'por_puesto': {clave: por_puesto[clave] for clave in sorted(por_puesto, key=int)},
        'por_tipo': {nombre: por_tipo[nombre] for nombre in RESUMEN_TIPOS_POR_ID.values() if nombre in por_tipo},
        'ventas_count': len(ventas) + len(libres),
    })

