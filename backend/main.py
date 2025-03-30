from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.country_code import CountryCode
from plaid.model.products import Products
from datetime import datetime, timedelta, date
import os
from dotenv import load_dotenv
from data_storage import DataStorage
import logging
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force reload environment variables
load_dotenv(override=True, verbose=True)  # Force reload and show what's being loaded

# Force sandbox environment
os.environ['PLAID_ENV'] = 'sandbox'

# Log environment variables (without exposing secrets)
logger.info("Environment variables loaded")
logger.info(f"PLAID_ENV: {os.getenv('PLAID_ENV', 'not set')}")
logger.info(f"PLAID_CLIENT_ID length: {len(os.getenv('PLAID_CLIENT_ID', ''))}")
logger.info(f"PLAID_SECRET length: {len(os.getenv('PLAID_SECRET', ''))}")

# Set Plaid environment
env = 'sandbox'  # Force sandbox mode
logger.info(f"Setting Plaid environment to: {env}")

if env == 'production':
    plaid_env = plaid.Environment.Production
    logger.info("Using Production environment")
else:
    plaid_env = plaid.Environment.Sandbox
    logger.info("Using Sandbox environment")

app = FastAPI(title="Personal Finance API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Plaid client
try:
    client_id = os.getenv('PLAID_CLIENT_ID')
    secret = os.getenv('PLAID_SECRET')
    
    if not client_id or not secret:
        raise ValueError("Plaid credentials not found in environment variables")
    
    logger.info(f"Initializing Plaid client with credentials for sandbox environment")
    logger.info(f"Using Client ID: {client_id}")
    logger.info(f"Using Secret length: {len(secret)}")
    
    configuration = plaid.Configuration(
        host=plaid.Environment.Sandbox,  # Force Sandbox environment
        api_key={
            'clientId': client_id,
            'secret': secret,
        }
    )
    api_client = plaid.ApiClient(configuration)
    plaid_client = plaid_api.PlaidApi(api_client)
    logger.info(f"Plaid client initialized successfully in Sandbox mode")
except Exception as e:
    logger.error(f"Failed to initialize Plaid client: {str(e)}")
    raise

# Initialize data storage
data_storage = DataStorage()

class Account(BaseModel):
    account_id: str
    name: str
    type: str
    balance: float
    currency_code: str

class Transaction(BaseModel):
    transaction_id: str
    amount: float
    date: datetime
    name: str
    category: Optional[List[str]]
    merchant_name: Optional[str]

class PublicTokenRequest(BaseModel):
    public_token: str
    user_id: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Welcome to Personal Finance API"}

@app.post("/create_link_token")
async def create_link_token():
    try:
        logger.info("Creating link token")
        
        # Verify Plaid client initialization
        if not plaid_client:
            raise ValueError("Plaid client not initialized")
            
        # Verify environment variables
        if not os.getenv('PLAID_CLIENT_ID') or not os.getenv('PLAID_SECRET'):
            raise ValueError("Plaid credentials not found in environment variables")
            
        # Generate a unique user ID for this session
        user_id = str(uuid.uuid4())
        logger.info(f"Generated unique user ID: {user_id}")
            
        # Create link token request with required fields
        request = LinkTokenCreateRequest(
            user={
                "client_user_id": user_id,  # Use the generated unique user ID
                "legal_name": "Weiyi Hu",
                "phone_number": "+16479700483",
                "email_address": "weiyi.henry.hu@gmail.com"
            },
            client_name="Personal Finance App",
            products=[Products("transactions")],
            country_codes=[CountryCode("CA")],
            language="en"
        )
        
        logger.info("Sending request to Plaid API with configuration:")
        logger.info(f"Client ID: {os.getenv('PLAID_CLIENT_ID')}")
        logger.info(f"User ID: {user_id}")
        logger.info(f"Environment: {plaid.Environment.Production}")
        logger.info(f"Products: {[Products('transactions')]}")
        logger.info(f"Country Codes: {[CountryCode('CA')]}")
        
        # Convert request to dict for logging (excluding sensitive data)
        request_dict = request.to_dict()
        logger.info(f"Request configuration: {request_dict}")
        
        try:
            response = plaid_client.link_token_create(request)
            logger.info(f"Raw response from Plaid: {response}")
        except plaid.ApiException as e:
            logger.error(f"Plaid API error details:")
            logger.error(f"Status Code: {e.status}")
            logger.error(f"Reason: {e.reason}")
            logger.error(f"Body: {e.body}")
            logger.error(f"Headers: {e.headers}")
            logger.error(f"Exception type: {type(e)}")
            raise
        
        if not response or 'link_token' not in response:
            logger.error("Invalid response from Plaid API")
            logger.error(f"Response content: {response}")
            raise ValueError("Invalid response from Plaid API")
            
        logger.info("Link token created successfully")
        return {"link_token": response['link_token']}
    except plaid.ApiException as e:
        logger.error(f"Plaid API error: Status Code: {e.status}")
        logger.error(f"Reason: {e.reason}")
        logger.error(f"Body: {e.body}")
        logger.error(f"Headers: {e.headers}")
        raise HTTPException(
            status_code=400,
            detail=f"Plaid API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating link token: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception details: {e.__dict__}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.post("/exchange_token")
async def exchange_public_token(request: PublicTokenRequest):
    try:
        logger.info(f"Attempting to exchange public token for user {request.user_id}")
        
        if not request.public_token:
            raise ValueError("Public token is required")
            
        exchange_request = ItemPublicTokenExchangeRequest(
            public_token=request.public_token
        )
        
        logger.info("Calling Plaid API to exchange token")
        exchange_response = plaid_client.item_public_token_exchange(exchange_request)
        access_token = exchange_response['access_token']
        logger.info("Successfully exchanged public token for access token")
        
        # Get account information
        logger.info("Fetching account information")
        accounts_request = AccountsGetRequest(access_token=access_token)
        accounts_response = plaid_client.accounts_get(accounts_request)
        accounts = accounts_response.to_dict()['accounts']
        logger.info(f"Retrieved {len(accounts)} accounts")
        
        # Get institution information
        try:
            institution_response = plaid_client.institutions_get_by_id(
                request_id=str(uuid.uuid4()),
                institution_id=exchange_response['item']['institution_id'],
                country_codes=[CountryCode("CA")]
            )
            institution_name = institution_response['institution']['name']
            logger.info(f"Retrieved institution name: {institution_name}")
            
            # Add institution name to each account
            for account in accounts:
                account['institution_name'] = institution_name
                logger.info(f"Added institution name '{institution_name}' to account {account.get('name', 'Unknown')}")
        except Exception as e:
            logger.warning(f"Failed to get institution name: {str(e)}")
            # If we can't get the institution name, use a default
            for account in accounts:
                account['institution_name'] = "Unknown Institution"
                logger.warning(f"Using default institution name 'Unknown Institution' for account {account.get('name', 'Unknown')}")
        
        # Save accounts with institution information
        logger.info("Saving account information")
        data_storage.save_accounts(request.user_id, accounts)
        
        # Wait for item to be ready before fetching transactions
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Get transaction information
                logger.info(f"Fetching transaction information (attempt {attempt + 1}/{max_retries})")
                
                # Use provided date range or default to 5 years
                if request.start_date and request.end_date:
                    start_date = datetime.strptime(request.start_date, '%Y-%m-%d').date()
                    end_date = datetime.strptime(request.end_date, '%Y-%m-%d').date()
                    logger.info(f"Using provided date range: {start_date} to {end_date}")
                else:
                    end_date = datetime.now().date()
                    start_date = end_date - timedelta(days=365*5)  # 5 years
                    logger.info(f"Using default date range: {start_date} to {end_date}")
                
                # Keep dates as date objects for Plaid API
                transactions_request = TransactionsGetRequest(
                    access_token=access_token,
                    start_date=start_date,
                    end_date=end_date,
                    options={"count": 500}  # Increased count to get more transactions
                )
                
                logger.info(f"Requesting transactions from {start_date} to {end_date}")
                transactions_response = plaid_client.transactions_get(transactions_request)
                transactions = transactions_response.to_dict()['transactions']
                logger.info(f"Retrieved {len(transactions)} transactions")
                
                # Convert dates to strings before saving to storage
                for transaction in transactions:
                    if 'date' in transaction and isinstance(transaction['date'], (datetime, date)):
                        transaction['date'] = transaction['date'].strftime('%Y-%m-%d')
                
                # Save transactions
                logger.info("Saving transaction information")
                data_storage.save_transactions(request.user_id, transactions)
                break  # Success, exit retry loop
                
            except plaid.ApiException as e:
                if e.status == 400 and "PRODUCT_NOT_READY" in str(e):
                    if attempt < max_retries - 1:
                        logger.info(f"Product not ready, waiting {retry_delay} seconds before retry...")
                        import time
                        time.sleep(retry_delay)
                        continue
                raise  # Re-raise if it's not a PRODUCT_NOT_READY error or we're out of retries
        
        logger.info("Data saved successfully")
        return {
            "message": "Successfully connected account",
            "institution_name": institution_name if 'institution_name' in locals() else "Unknown Institution"
        }
        
    except plaid.ApiException as e:
        logger.error(f"Plaid API error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Plaid API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/accounts/{user_id}")
async def get_accounts(user_id: str):
    try:
        accounts = data_storage.get_accounts(user_id)
        return {"accounts": accounts}
    except Exception as e:
        logger.error(f"Error getting accounts: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/transactions/{user_id}")
async def get_transactions(user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    try:
        # If no dates provided, default to last 30 days
        if not start_date or not end_date:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            # Convert string dates to date objects
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
        # Validate date range (max 10 years)
        max_date_range = timedelta(days=3650)  # 10 years
        if (end_date - start_date) > max_date_range:
            raise HTTPException(
                status_code=400,
                detail="Date range cannot exceed 10 years"
            )
            
        transactions = data_storage.get_transactions(user_id, start_date, end_date)
        return {"transactions": transactions}
    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error getting transactions: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/summary/{user_id}")
async def get_summary(user_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    try:
        # If no dates provided, default to last 30 days
        if not start_date or not end_date:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            # Convert string dates to date objects
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
        # Validate date range (max 10 years)
        max_date_range = timedelta(days=3650)  # 10 years
        if (end_date - start_date) > max_date_range:
            raise HTTPException(
                status_code=400,
                detail="Date range cannot exceed 10 years"
            )
            
        summary = data_storage.get_account_summary(user_id, start_date, end_date)
        return summary
    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Error getting summary: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/clean_test_data")
async def clean_test_data(user_id: Optional[str] = None):
    """Clean out test data. If user_id is provided, only clean that user's data."""
    try:
        data_storage.clean_test_data(user_id)
        return {"message": "Test data cleaned successfully"}
    except Exception as e:
        logger.error(f"Error cleaning test data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error cleaning test data: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000) 