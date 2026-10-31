from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

class AccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_user_registration(self):
        url = '/api/accounts/register/'
        data = {'username': 'testuser', 'email': 'test@example.com', 'password': 'testpassword'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().username, 'testuser')

    def test_weak_password_does_not_provision_records(self):
        from marketplace.models import Cart
        from accounts.models import Profile
        response = self.client.post('/api/accounts/register/', {'username': 'weak', 'email': 'weak@example.com', 'password': '1'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Profile.objects.count(), 0)
        self.assertEqual(Cart.objects.count(), 0)

    def test_refresh_rotation_rejects_replay(self):
        User.objects.create_user('rotating', password='long-test-password-572!')
        response = self.client.post('/api/accounts/token/', {'username': 'rotating', 'password': 'long-test-password-572!'})
        self.assertEqual(response.status_code, 200)
        refresh = response.data['refresh']
        rotated = self.client.post('/api/accounts/token/refresh/', {'refresh': refresh})
        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(rotated.data['refresh'], refresh)
        self.assertEqual(self.client.post('/api/accounts/token/refresh/', {'refresh': refresh}).status_code, 401)

    @override_settings(
        ACCOUNT_RESET_URL='https://unihome.example/reset',
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_recovery_is_single_use_and_invalidates_jwt(self):
        from django.core import mail
        from urllib.parse import urlsplit, parse_qs
        user = User.objects.create_user('recover', email='recover@example.com', password='before-reset-572!')
        pair = self.client.post('/api/accounts/token/', {'username': user.username, 'password': 'before-reset-572!'}).data
        known = self.client.post('/api/accounts/password-reset/', {'email': user.email})
        unknown = self.client.post('/api/accounts/password-reset/', {'email': 'missing@example.com'})
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        query = parse_qs(urlsplit(mail.outbox[0].body.split()[-1]).query)
        payload = {k: v[0] for k, v in query.items()}
        payload['password'] = 'after-reset-Strong-903!'
        self.assertEqual(self.client.post('/api/accounts/password-reset/confirm/', payload).status_code, 200)
        self.assertEqual(self.client.post('/api/accounts/password-reset/confirm/', payload).status_code, 400)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + pair['access'])
        self.assertEqual(self.client.get(f'/api/marketplace/cart/{user.cart.pk}/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/accounts/token/refresh/', {'refresh': pair['refresh']}).status_code, 401)
