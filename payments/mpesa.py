import requests
import base64
from datetime import datetime
from decimal import Decimal
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MPesaClient:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.callback_url = settings.MPESA_CALLBACK_URL
        print("Callback URL:", self.callback_url)
        if settings.MPESA_ENV == 'sandbox':
            self.base_url = 'https://sandbox.safaricom.co.ke'
        else:
            self.base_url = 'https://api.safaricom.co.ke'
    
    def get_access_token(self):
        url = f'{self.base_url}/oauth/v1/generate?grant_type=client_credentials'
        auth = base64.b64encode(f'{self.consumer_key}:{self.consumer_secret}'.encode()).decode()
        headers = {'Authorization': f'Basic {auth}'}
        
        response = requests.get(url, headers=headers)
        return response.json().get('access_token')
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc):
        access_token = self.get_access_token()
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            f'{self.shortcode}{self.passkey}{timestamp}'.encode()
        ).decode()
        
        url = f'{self.base_url}/mpesa/stkpush/v1/processrequest'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }

        
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': timestamp,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': self.usd_to_kes(amount),
            'PartyA': phone_number,
            'PartyB': self.shortcode,
            'PhoneNumber': phone_number,
            'CallBackURL': self.callback_url,
            'AccountReference': account_reference,
            'TransactionDesc': transaction_desc
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def get_usd_to_kes_rate(self):
        """Get current USD to KES exchange rate with caching"""
        # Check cache first (cache for 1 hour)
        cached_rate = cache.get('usd_to_kes_rate')
        if cached_rate:
            return Decimal(cached_rate)
        
        try:
            # Free API - no key required for basic use
            url = 'https://api.exchangerate-api.com/v4/latest/USD'
            response = requests.get(url, timeout=5)
            data = response.json()
            
            rate = Decimal(str(data['rates']['KES']))
            
            # Cache for 1 hour (3600 seconds)
            cache.set('usd_to_kes_rate', str(rate), 3600)
            
            return rate
        except Exception as e:
            # Fallback to approximate rate if API fails
            logger.warning(f"Failed to fetch exchange rate: {e}")
            return Decimal('129.50')  # Approximate fallback rate
        
    def usd_to_kes(self, usd_amount):
        """Convert USD to KES"""
        rate = self.get_usd_to_kes_rate()
        kes_amount = Decimal(str(usd_amount)) * rate
        return int(kes_amount)  # M-Pesa requires integer
