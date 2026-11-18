"""Settings para pruebas: SQLite en memoria, jamás la BD de producción del .env.
Uso: python manage.py test --settings=inventario.settings_test
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
