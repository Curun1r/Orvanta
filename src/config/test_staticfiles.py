import gzip
import json
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.http import HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase
from whitenoise.middleware import WhiteNoiseMiddleware

from .settings import STORAGES as PRODUCTION_STORAGES


class ProductionStaticFilesTests(SimpleTestCase):
    def test_collected_assets_are_hashed_compressed_and_served_with_cache_headers(self):
        with TemporaryDirectory() as static_root, self.settings(
            DEBUG=False, STATIC_ROOT=static_root, STORAGES=PRODUCTION_STORAGES,
        ):
            call_command('collectstatic', interactive=False, verbosity=0)
            manifest = json.loads((Path(static_root) / 'staticfiles.json').read_text())
            middleware = WhiteNoiseMiddleware(lambda request: HttpResponse(status=404))
            factory = RequestFactory()

            for name in ('css/styles.css', 'js/auth.js', 'img/orvanta-wordmark.svg'):
                with self.subTest(asset=name):
                    hashed_name = manifest['paths'][name]
                    self.assertNotEqual(hashed_name, name)
                    self.assertTrue((Path(static_root) / hashed_name).is_file())
                    url = staticfiles_storage.url(name)
                    self.assertTrue(url.endswith(hashed_name))
                    rendered = Template('{% load static %}{% static asset %}').render(
                        Context({'asset': name}),
                    )
                    self.assertEqual(rendered, url)
                    with closing(middleware(factory.get(url))) as response:
                        self.assertEqual(response.status_code, 200)
                        self.assertIn('immutable', response['Cache-Control'])

            css_name = manifest['paths']['css/styles.css']
            css = (Path(static_root) / css_name).read_bytes()
            with closing(middleware(factory.get(
                staticfiles_storage.url('css/styles.css'), HTTP_ACCEPT_ENCODING='gzip',
            ))) as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Encoding'], 'gzip')
                self.assertIn('Accept-Encoding', response['Vary'])
                self.assertEqual(gzip.decompress(b''.join(response.streaming_content)), css)

            for path in ('/login/', '/signup/'):
                with self.subTest(page=path):
                    response = self.client.get(path)
                    self.assertContains(response, staticfiles_storage.url('css/styles.css'))
                    self.assertContains(response, staticfiles_storage.url('js/auth.js'))
