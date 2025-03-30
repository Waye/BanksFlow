import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get credentials from environment variables
client_id = os.getenv('PLAID_CLIENT_ID')
secret = os.getenv('PLAID_SECRET')

# API endpoint
url = 'https://sandbox.plaid.com/link/token/create'

# Request payload
payload = {
    'client_id': client_id,
    'secret': secret,
    'client_name': 'Personal Finance App',
    'country_codes': ['US'],
    'language': 'en',
    'user': {
        'client_user_id': 'test_user_1'
    },
    'products': ['transactions']
}

# Make the request
response = requests.post(url, json=payload)

# Print the response
print(f'Status code: {response.status_code}')
print('Response:')
print(json.dumps(response.json(), indent=2)) 