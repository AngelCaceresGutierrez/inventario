from datetime import datetime, timezone
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import AsociacionProducto, PendienteProducto, Productos, Tipo, Ventas, VentasLibres

# Con los settings normales el runner crearía test_<db> en el servidor de producción.
if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise ImproperlyConfigured(
        'Pruebas solo sobre SQLite: python manage.py test --settings=inventario.settings_test'
    )

FECHA = '2026-11-17'
MOMENTO = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
ROPA, PAQUETERIA, UTILES = 1, 2, 3


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
        cls.polera = Productos.objects.create(pro_nombre='Polera', pro_precio=9999, pro_tipo_id=ROPA)
        cls.cinta = Productos.objects.create(pro_nombre='Cinta', pro_precio=8888, pro_tipo_id=PAQUETERIA)
        cls.sin_tipo = Productos.objects.create(pro_nombre='Varios', pro_precio=7777, pro_tipo_id=None)

    def _libre(self, nombre, valor, puesto=1):
        return VentasLibres.objects.create(
            vl_nombre=nombre, vl_valor=valor, vl_fecha_registro=MOMENTO, vl_puesto=puesto,
        )

    def _asociar(self, texto, producto):
        return AsociacionProducto.objects.create(ap_texto=texto, ap_producto=producto, ap_fecha=MOMENTO)

    def _resumen(self):
        respuesta = self.client.get(reverse('resumen_gerencia'), {'nivel': 'dia', 'fecha': FECHA})
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.json()

    def test_libre_asociada_suma_vl_valor_y_no_pro_precio(self):
        self._asociar('polera', self.polera)
        self._libre('polera', 1500)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 1500})

    def test_libre_sin_asociacion_no_entra_en_por_tipo_pero_si_en_total(self):
        self._libre('cosa desconocida', 1200)

        resumen = self._resumen()

        self.assertEqual(resumen['por_tipo'], {})
        self.assertEqual(resumen['total'], 1200)

    def test_nombre_con_mayusculas_acentos_y_espacios_resuelve(self):
        self._asociar('polera nino', self.polera)
        self._libre('  POLERA   Niño ', 2000)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 2000})

    def test_producto_sin_tipo_no_entra_en_por_tipo_pero_si_en_total(self):
        self._asociar('varios', self.sin_tipo)
        self._libre('varios', 700)

        resumen = self._resumen()

        self.assertEqual(resumen['por_tipo'], {})
        self.assertEqual(resumen['total'], 700)

    def test_varias_libres_acumulan_separadas_por_tipo(self):
        self._asociar('polera', self.polera)
        self._asociar('cinta', self.cinta)
        self._libre('polera', 1000)
        self._libre('Polera', 500, puesto=2)
        self._libre('cinta', 300)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 1500, 'Paqueteria': 300})

    def test_venta_antigua_y_libre_acumulan_en_el_mismo_tipo(self):
        Ventas.objects.create(
            ven_fecha_registro=MOMENTO, ven_productos=f'{self.polera.pro_id}_1', ven_puesto=1,
        )
        self._asociar('polera', self.polera)
        self._libre('polera', 1500)

        self.assertEqual(self._resumen()['por_tipo'], {'Ropa': 9999 + 1500})

    def test_asociar_pendiente_incluye_ventas_pasadas_sin_cambiar_totales(self):
        self._libre('Polera Niño', 1500)
        self._libre('sin asociar', 400, puesto=2)
        antes = self._resumen()
        self.assertEqual(antes['por_tipo'], {})

        respuesta = self.client.post(
            reverse('asociar_pendiente'),
            {'texto': 'Polera Niño', 'producto_id': self.polera.pro_id},
            content_type='application/json',
        )
        self.assertEqual(respuesta.status_code, 200)

        despues = self._resumen()
        self.assertEqual(despues['por_tipo'], {'Ropa': 1500})
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
