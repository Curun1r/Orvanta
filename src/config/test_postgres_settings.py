"""Run the full suite against an explicitly selected, disposable PostgreSQL server."""

import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .test_settings import *  # noqa: F401,F403


database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise ImproperlyConfigured('PostgreSQL tests require an explicit DATABASE_URL.')

database = dj_database_url.parse(database_url, conn_max_age=0)
if database['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('PostgreSQL tests require a PostgreSQL DATABASE_URL.')

# The test runner creates this database on the disposable server and removes it afterward.
database['TEST'] = {'NAME': 'test_orvanta_ci'}
DATABASES = {'default': database}
