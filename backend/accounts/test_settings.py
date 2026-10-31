import os
import subprocess
import sys
from pathlib import Path
from django.test import SimpleTestCase


class ConfigurationTests(SimpleTestCase):
    def check_config(self, **overrides):
        values = os.environ.copy()
        for name in ['DJANGO_SECRET_KEY', 'DJANGO_DEBUG', 'DJANGO_ALLOWED_HOSTS']:
            values.pop(name, None)
        values.update(overrides)
        return subprocess.run([sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'], cwd=Path(__file__).resolve().parents[1], env=values, capture_output=True, text=True)

    def test_missing_secret_fails_closed(self):
        result = self.check_config()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set DJANGO_SECRET_KEY', result.stderr)

    def test_production_requires_explicit_hosts(self):
        result = self.check_config(DJANGO_SECRET_KEY='x' * 60)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('explicit allowed hosts', result.stderr)

    def test_production_settings_pass_deployment_checks(self):
        result = self.check_config(DJANGO_SECRET_KEY='test-only-strong-shape-secret-1234567890-abcdefghijklmnopqrstuvwxyz', DJANGO_ALLOWED_HOSTS='unihome.example', DJANGO_HSTS_INCLUDE_SUBDOMAINS='true', DJANGO_HSTS_PRELOAD='true')
        self.assertEqual(result.returncode, 0, result.stderr)
