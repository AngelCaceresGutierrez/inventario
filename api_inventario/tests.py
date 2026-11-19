from datetime import datetime, timezone
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import AsociacionProducto, Dueno, PendienteProducto, Productos, Tipo, Ventas, VentasLibres

# Con los settings normales el runner crearía test_<db> en el servidor de producción.
if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise ImproperlyConfigured(
        'Pruebas solo sobre SQLite: python manage.py test --settings=inventario.settings_test'
    )

FECHA = '2026-11-17'
MOMENTO = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
ROPA, PAQUETERIA, UTILES = 1, 2, 3
MIREYA = 1


def setUpModule():
    """Los modelos son managed=False: el runner no crea sus tablas."""
    with connection.schema_editor() as editor:
        for modelo in apps.get_app_config('api_inventario').get_models():
            editor.create_model(modelo)


class ResumenGerenciaPorTipoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for tip_id, nombre in ((ROPA, 'Ropa'), (PAQUETERIA, 'Paqueteria'), (UTILES, 'Utiles escolares')):
            Tipo.objects.create(tip_id=tip_id, tip_nombre=nombre)
        Dueno.objects.create(due_id=MIREYA, due_nombre='Mireya')
        cls.polera = cls._producto('Polera', 9999, ROPA)
        cls.cinta = cls._producto('Cinta', 8888, PAQUETERIA)
        cls.sin_tipo = cls._producto('Varios', 7777, None)

    @staticmethod
    def _producto(nombre, precio, tipo, dueno=MIREYA):
        return Productos.objects.create(pro_nombre=nombre, pro_precio=precio, pro_tipo_id=tipo, pro_dueno_id=dueno)

    def _libre(self, nombre, valor, puesto=1, momento=MOMENTO):
        return VentasLibres.objects.create(
            vl_nombre=nombre, vl_valor=valor, vl_fecha_registro=momento, vl_puesto=puesto,
        )

    def _venta_antigua(self, producto, cantidad=1):
        return Ventas.objects.create(
            ven_fecha_registro=MOMENTO, ven_productos=f'{producto.pro_id}_{cantidad}', ven_puesto=1,
        )

    def _asociar(self, texto, producto):
        return AsociacionProducto.objects.create(ap_texto=texto, ap_producto=producto, ap_fecha=MOMENTO)

    def _resumen(self, nivel='dia'):
        respuesta = self.client.get(reverse('resumen_gerencia'), {'nivel': nivel, 'fecha': FECHA})
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.json()

    def test_libre_asociada_suma_vl_valor_y_no_pro_precio(self):
        self._asociar('polera', self.polera)
        self._libre('polera', 1500)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 1500})

    def test_libre_sin_asociacion_ni_producto_va_a_sin_tipo(self):
        self._libre('cosa desconocida', 1200)

        resumen = self._resumen()

        self.assertEqual(resumen['por_tipo'], {'Sin tipo': 1200})
        self.assertEqual(resumen['total'], 1200)

    def test_nombre_con_mayusculas_acentos_y_espacios_resuelve(self):
        self._asociar('polera nino', self.polera)
        self._libre('  POLERA   Niño ', 2000)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 2000})

    def test_producto_asociado_sin_tipo_va_a_sin_tipo(self):
        self._asociar('varios', self.sin_tipo)
        self._libre('varios', 700)

        resumen = self._resumen()

        self.assertEqual(resumen['por_tipo'], {'Sin tipo': 700})
        self.assertEqual(resumen['total'], 700)

    def test_varias_libres_acumulan_separadas_por_tipo(self):
        self._asociar('polera', self.polera)
        self._asociar('cinta', self.cinta)
        self._libre('polera', 1000)
        self._libre('Polera', 500, puesto=2)
        self._libre('cinta', 300)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 1500, 'Paqueteria': 300})

    def test_venta_antigua_y_libre_acumulan_en_el_mismo_tipo(self):
        self._venta_antigua(self.polera)
        self._asociar('polera', self.polera)
        self._libre('polera', 1500)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 9999 + 1500})

    def test_asociar_pendiente_incluye_ventas_pasadas_sin_cambiar_totales(self):
        self._libre('Polera Niño', 1500)
        self._libre('sin asociar', 400, puesto=2)
        antes = self._resumen()
        self.assertEqual(antes['por_tipo'], {'Sin tipo': 1900})

        respuesta = self.client.post(
            reverse('asociar_pendiente'),
            {'texto': 'Polera Niño', 'producto_id': self.polera.pro_id},
            content_type='application/json',
        )
        self.assertEqual(respuesta.status_code, 200)

        despues = self._resumen()
        self.assertEqual(despues['por_tipo'], {'Ropa': 1500, 'Sin tipo': 400})
        for campo in ('total', 'serie', 'por_dueno', 'por_puesto', 'ventas_count'):
            self.assertEqual(despues[campo], antes[campo], campo)

    def test_numero_de_queries_no_crece_con_la_cantidad_de_libres(self):
        self._asociar('texto 0', self.polera)
        self._libre('texto 0', 100)
        with CaptureQueriesContext(connection) as con_una_libre:
            self._resumen()

        for indice in range(1, 30):
            self._asociar(f'texto {indice}', self.cinta)
            self._libre(f'texto {indice}', 100)
        with CaptureQueriesContext(connection) as con_treinta_libres:
            resumen = self._resumen()

        self.assertEqual(len(con_treinta_libres), len(con_una_libre))
        self.assertEqual(resumen['por_tipo'], {'Ropa': 100, 'Paqueteria': 2900})

    def test_ejemplo_del_usuario_romy_y_parche_curita(self):
        self._producto('Parche Curita', 300, PAQUETERIA)
        self._libre('romy', 2000)
        self._libre('parche curita', 1500)

        resumen = self._resumen()

        self.assertEqual(resumen['por_tipo'], {'Paqueteria': 1500, 'Sin tipo': 2000})
        self.assertEqual(resumen['total'], 3500)

    def test_nombre_de_producto_con_acentos_resuelve_sin_asociacion(self):
        self._producto('Cuadérno  Grande', 100, UTILES)
        self._libre('CUADERNO grande', 900)

        self.assertEqual(self._resumen()['por_tipo'], {'Utiles escolares': 900})

    def test_asociacion_tiene_prioridad_sobre_nombre_de_producto(self):
        self._asociar('cinta', self.polera)
        self._libre('cinta', 600)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 600})

    def test_asociacion_sin_tipo_cae_a_busqueda_por_nombre(self):
        self._asociar('cinta', self.sin_tipo)
        self._libre('cinta', 600)

        self.assertEqual(self._resumen()['por_tipo'], {'Paqueteria': 600})

    def test_nombre_ambiguo_entre_tipos_va_a_sin_tipo(self):
        self._producto('Lapiz', 100, ROPA)
        self._producto('LÁPIZ', 200, UTILES)
        self._libre('lapiz', 800)

        self.assertEqual(self._resumen()['por_tipo'], {'Sin tipo': 800})

    def test_duplicado_sin_tipo_no_anula_el_tipo_conocido(self):
        self._producto('CINTA', 200, None)
        self._libre('cinta', 1500)

        self.assertEqual(self._resumen()['por_tipo'], {'Paqueteria': 1500})

    def test_duplicado_con_tipo_fuera_del_catalogo_no_anula_el_tipo_conocido(self):
        Tipo.objects.create(tip_id=99, tip_nombre='Otro')
        self._producto('CINTA', 200, 99)
        self._libre('cinta', 1500)

        self.assertEqual(self._resumen()['por_tipo'], {'Paqueteria': 1500})

    def test_nombre_repetido_con_el_mismo_tipo_no_es_ambiguo(self):
        self._producto('Lapiz', 100, UTILES)
        self._producto('LÁPIZ', 200, UTILES)
        self._libre('lapiz', 800)

        self.assertEqual(self._resumen()['por_tipo'], {'Utiles escolares': 800})

    def test_producto_encontrado_por_nombre_sin_tipo_va_a_sin_tipo(self):
        self._libre('varios', 700)

        self.assertEqual(self._resumen()['por_tipo'], {'Sin tipo': 700})

    def test_libre_de_puesto_sin_dueno_no_descuadra(self):
        self._libre('polera', 1000)
        self._libre('polera', 5000, puesto=3)

        resumen = self._resumen()

        self.assertEqual(resumen['por_tipo'], {'Ropa': 1000})
        self.assertEqual(resumen['total'], 1000)
        self.assertEqual(resumen['por_puesto'], {'1': 1000, '3': 5000})

    def test_ventas_antiguas_con_tipo_sin_tipo_y_sin_dueno(self):
        self._venta_antigua(self.polera)
        self._venta_antigua(self.sin_tipo)
        self._venta_antigua(self._producto('Sin dueno', 4000, ROPA, dueno=None))

        resumen = self._resumen()

        self.assertEqual(resumen['por_tipo'], {'Ropa': 9999, 'Sin tipo': 7777})
        self.assertEqual(resumen['total'], 9999 + 7777)

    def test_por_tipo_respeta_el_orden_y_omite_montos_en_cero(self):
        self._producto('Cuaderno', 100, UTILES)
        self._libre('romy', 10)
        self._libre('cuaderno', 20)
        self._libre('cinta', 30)
        self._libre('polera', 40)

        self.assertEqual(
            list(self._resumen()['por_tipo'].items()),
            [('Ropa', 40), ('Paqueteria', 30), ('Utiles escolares', 20), ('Sin tipo', 10)],
        )

    def test_libre_con_valor_cero_no_crea_clave(self):
        self._libre('romy', 0)

        self.assertEqual(self._resumen()['por_tipo'], {})

    def test_suma_de_tipos_es_igual_al_total_en_cada_nivel(self):
        self._venta_antigua(self.polera, cantidad=2)
        self._venta_antigua(self.sin_tipo)
        self._venta_antigua(self._producto('Sin dueno', 4000, ROPA, dueno=None))
        self._libre('romy', 2000)
        self._libre('cinta', 1500, puesto=2)
        self._libre('polera', 5000, puesto=3)
        self._libre('polera', 700, momento=datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc))
        self._libre('cinta', 300, momento=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc))

        base_dia = 2 * 9999 + 7777 + 2000 + 1500
        for nivel, esperado in (('dia', base_dia), ('semana', base_dia + 700), ('mes', base_dia + 1000)):
            with self.subTest(nivel=nivel):
                resumen = self._resumen(nivel)
                self.assertEqual(resumen['total'], esperado)
                self.assertEqual(sum(resumen['por_tipo'].values()), resumen['total'])

    def test_una_sola_query_de_productos_sin_importar_la_cantidad_de_ventas(self):
        self._producto('nombre 0', 100, ROPA)
        self._libre('nombre 0', 100)
        self._venta_antigua(self.polera)
        with CaptureQueriesContext(connection) as con_una_libre:
            self._resumen()

        for indice in range(1, 30):
            self._producto(f'nombre {indice}', 100, PAQUETERIA)
            self._libre(f'nombre {indice}', 100)
            self._venta_antigua(self.cinta)
        with CaptureQueriesContext(connection) as con_treinta_libres:
            self._resumen()

        consultas_de_productos = [q for q in con_treinta_libres if 'FROM "productos"' in q['sql']]
        self.assertEqual(len(consultas_de_productos), 1)
        self.assertEqual(len(con_treinta_libres), len(con_una_libre))


class MetodoPagoCrearVentaLibreTests(TestCase):
    ITEMS = [{'nombre': 'gasa', 'valor': 500}, {'nombre': 'curita', 'valor': 1000}]

    def _crear(self, **extra):
        return self.client.post(
            reverse('crear_venta_libre'), {'puesto': 1, 'items': self.ITEMS, **extra}, content_type='application/json',
        )

    def _metodos_guardados(self):
        return list(VentasLibres.objects.values_list('vl_metodo_pago', flat=True))

    def test_cada_metodo_se_guarda_en_todas_las_filas(self):
        for metodo in ('efectivo', 'tarjeta', 'transferencia'):
            with self.subTest(metodo=metodo):
                VentasLibres.objects.all().delete()

                respuesta = self._crear(metodo_pago=metodo)

                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(self._metodos_guardados(), [metodo, metodo])

    def test_sin_metodo_de_pago_guarda_efectivo(self):
        self.assertEqual(self._crear().status_code, 200)

        self.assertEqual(self._metodos_guardados(), ['efectivo', 'efectivo'])

    def test_metodo_invalido_responde_400_sin_guardar_nada(self):
        for invalido in ('cheque', 'Tarjeta', '', 1, True, None, ['tarjeta'], {'metodo': 'tarjeta'}):
            with self.subTest(invalido=invalido):
                respuesta = self._crear(metodo_pago=invalido)

                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json()['codigo'], 'PAYLOAD_INVALIDO')
                self.assertEqual(VentasLibres.objects.count(), 0)
                self.assertEqual(PendienteProducto.objects.count(), 0)

    def test_respuesta_no_cambia_al_enviar_metodo(self):
        self.assertEqual(self._crear(metodo_pago='tarjeta').json(), {
            'message': 'Ventas libres creadas',
            'ventas_creadas': 2,
            'asociaciones': {'auto': 0, 'pendientes': 2},
        })


class ResumenGerenciaMetodoPagoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Tipo.objects.create(tip_id=ROPA, tip_nombre='Ropa')
        Dueno.objects.create(due_id=MIREYA, due_nombre='Mireya')
        cls.con_dueno = Productos.objects.create(
            pro_nombre='Polera', pro_precio=9999, pro_tipo_id=ROPA, pro_dueno_id=MIREYA,
        )
        cls.sin_dueno = Productos.objects.create(pro_nombre='Huerfano', pro_precio=4000, pro_tipo_id=ROPA)

    def _libre(self, valor, metodo='efectivo', puesto=1, momento=MOMENTO):
        return VentasLibres.objects.create(
            vl_nombre='romy', vl_valor=valor, vl_fecha_registro=momento, vl_puesto=puesto, vl_metodo_pago=metodo,
        )

    def _venta_antigua(self, producto):
        return Ventas.objects.create(ven_fecha_registro=MOMENTO, ven_productos=f'{producto.pro_id}_1', ven_puesto=1)

    def _resumen(self, nivel='dia'):
        respuesta = self.client.get(reverse('resumen_gerencia'), {'nivel': nivel, 'fecha': FECHA})
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.json()

    def test_sin_ventas_llegan_las_tres_claves_en_cero(self):
        self.assertEqual(self._resumen()['por_metodo_pago'], {'efectivo': 0, 'tarjeta': 0, 'transferencia': 0})

    def test_metodo_sin_ventas_llega_en_cero(self):
        self._libre(1500, 'tarjeta')

        self.assertEqual(self._resumen()['por_metodo_pago'], {'efectivo': 0, 'tarjeta': 1500, 'transferencia': 0})

    def test_suma_vl_valor_por_metodo(self):
        self._libre(100, 'efectivo')
        self._libre(200, 'tarjeta')
        self._libre(300, 'tarjeta', puesto=2)
        self._libre(400, 'transferencia')

        self.assertEqual(self._resumen()['por_metodo_pago'], {'efectivo': 100, 'tarjeta': 500, 'transferencia': 400})

    def test_venta_antigua_cuenta_como_efectivo(self):
        self._venta_antigua(self.con_dueno)

        self.assertEqual(self._resumen()['por_metodo_pago'], {'efectivo': 9999, 'tarjeta': 0, 'transferencia': 0})

    def test_montos_sin_dueno_no_cuentan(self):
        self._venta_antigua(self.sin_dueno)
        self._libre(5000, 'tarjeta', puesto=3)

        resumen = self._resumen()

        self.assertEqual(resumen['por_metodo_pago'], {'efectivo': 0, 'tarjeta': 0, 'transferencia': 0})
        self.assertEqual(resumen['total'], 0)

    def test_suma_de_metodos_es_igual_al_total_en_cada_nivel(self):
        self._venta_antigua(self.con_dueno)
        self._venta_antigua(self.sin_dueno)
        self._libre(2000, 'efectivo')
        self._libre(1500, 'tarjeta', puesto=2)
        self._libre(5000, 'transferencia', puesto=3)
        self._libre(700, 'transferencia', momento=datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc))
        self._libre(300, 'tarjeta', momento=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc))

        base_dia = 9999 + 2000 + 1500
        for nivel, esperado in (('dia', base_dia), ('semana', base_dia + 700), ('mes', base_dia + 1000)):
            with self.subTest(nivel=nivel):
                resumen = self._resumen(nivel)
                self.assertEqual(resumen['total'], esperado)
                self.assertEqual(sum(resumen['por_metodo_pago'].values()), resumen['total'])
                self.assertEqual(sum(resumen['por_tipo'].values()), resumen['total'])

    def test_numero_de_queries_no_crece_con_la_cantidad_de_ventas(self):
        self._libre(100, 'tarjeta')
        with CaptureQueriesContext(connection) as con_una_venta:
            self._resumen()

        for _ in range(30):
            self._libre(100, 'transferencia')
        with CaptureQueriesContext(connection) as con_treinta_ventas:
            self._resumen()

        self.assertEqual(len(con_treinta_ventas), len(con_una_venta))


class CrearVentaLibreTests(TestCase):
    ITEMS_VALIDOS = [{'nombre': 'gasa', 'valor': 500}, {'nombre': 'curita', 'valor': 1000}, {'nombre': 'polera', 'valor': 2000}]

    @classmethod
    def setUpTestData(cls):
        cls.polera = Productos.objects.create(pro_nombre='Polera', pro_precio=9999)

    def _crear(self, items, puesto=1):
        return self.client.post(
            reverse('crear_venta_libre'), {'puesto': puesto, 'items': items}, content_type='application/json',
        )

    def _assert_sin_escrituras(self):
        self.assertEqual(VentasLibres.objects.count(), 0)
        self.assertEqual(AsociacionProducto.objects.count(), 0)
        self.assertEqual(PendienteProducto.objects.count(), 0)

    def test_valor_fuera_de_int4_responde_400_sin_guardar_nada(self):
        items = self.ITEMS_VALIDOS[:2] + [{'nombre': 'polera', 'valor': 99999999999}]

        respuesta = self._crear(items)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()['codigo'], 'PAYLOAD_INVALIDO')
        self._assert_sin_escrituras()

    def test_primer_valor_sobre_el_limite_int4_se_rechaza(self):
        self.assertEqual(self._crear([{'nombre': 'gasa', 'valor': 2147483648}]).status_code, 400)
        self._assert_sin_escrituras()

    def test_valor_en_el_limite_int4_se_acepta(self):
        self.assertEqual(self._crear([{'nombre': 'gasa', 'valor': 2147483647}]).status_code, 200)
        self.assertEqual(VentasLibres.objects.get().vl_valor, 2147483647)

    @patch('api_inventario.views.traceback.print_exc')
    def test_fallo_a_mitad_del_bucle_no_deja_filas_parciales(self, _print_exc):
        # 1er ítem crea asociación, 2do crea pendiente, 3ro revienta.
        with patch('api_inventario.views._mejor_match_producto', side_effect=[self.polera.pro_id, None, RuntimeError]):
            respuesta = self._crear(self.ITEMS_VALIDOS)

        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(respuesta.json()['codigo'], 'ERROR_BD')
        self._assert_sin_escrituras()

    @patch('api_inventario.views.traceback.print_exc')
    def test_reintento_tras_fallo_no_duplica_ventas(self, _print_exc):
        with patch('api_inventario.views._mejor_match_producto', side_effect=[None, RuntimeError]):
            self._crear(self.ITEMS_VALIDOS)

        self.assertEqual(self._crear(self.ITEMS_VALIDOS).status_code, 200)

        self.assertEqual(VentasLibres.objects.count(), 3)

    def test_venta_valida_mantiene_el_contrato_de_respuesta(self):
        respuesta = self._crear(self.ITEMS_VALIDOS)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {
            'message': 'Ventas libres creadas',
            'ventas_creadas': 3,
            'asociaciones': {'auto': 1, 'pendientes': 2},
        })
        self.assertEqual(VentasLibres.objects.count(), 3)
        self.assertEqual(AsociacionProducto.objects.get().ap_producto_id, self.polera.pro_id)
        self.assertEqual(PendienteProducto.objects.count(), 2)
