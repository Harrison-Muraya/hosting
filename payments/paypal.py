import requests
from django.conf import settings

class PayPalClient:
    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        
        if settings.PAYPAL_MODE == 'sandbox':
            self.base_url = 'https://api-m.sandbox.paypal.com'
        else:
            self.base_url = 'https://api-m.paypal.com'
    
    def get_access_token(self):
        url = f'{self.base_url}/v1/oauth2/token'
        headers = {'Accept': 'application/json'}
        data = {'grant_type': 'client_credentials'}
        
        response = requests.post(
            url, 
            auth=(self.client_id, self.client_secret),
            headers=headers,
            data=data
        )
        return response.json().get('access_token')
    
    def create_order(self, amount, currency='USD', return_url='', cancel_url=''):
        access_token = self.get_access_token()
        url = f'{self.base_url}/v2/checkout/orders'
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        payload = {
            'intent': 'CAPTURE',
            'purchase_units': [{
                'amount': {
                    'currency_code': currency,
                    'value': str(amount)
                }
            }],
            'application_context': {
                'return_url': return_url,
                'cancel_url': cancel_url
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def capture_order(self, order_id):
        access_token = self.get_access_token()
        url = f'{self.base_url}/v2/checkout/orders/{order_id}/capture'
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.post(url, headers=headers)
        return response.json()