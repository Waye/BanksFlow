import json
import os
from datetime import datetime, timedelta, date
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class DataStorage:
    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = storage_dir
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """Ensure storage directory exists"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def _get_user_file(self, user_id: str, data_type: str) -> str:
        return os.path.join(self.storage_dir, f"{user_id}_{data_type}.json")

    def save_accounts(self, user_id: str, accounts: List[Dict[str, Any]]):
        """Save account information"""
        file_path = self._get_user_file(user_id, "accounts")
        
        # Get existing accounts if any
        existing_accounts = []
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                existing_accounts = data.get("accounts", [])
        
        # Create a set of existing account IDs
        existing_account_ids = {acc.get("account_id") for acc in existing_accounts}
        
        # Filter out new accounts that already exist
        new_accounts = [
            acc for acc in accounts 
            if acc.get("account_id") not in existing_account_ids
        ]
        
        # Combine existing and new accounts
        all_accounts = existing_accounts + new_accounts
        
        # Ensure each account has an institution_name
        for account in all_accounts:
            if "institution_name" not in account:
                account["institution_name"] = "Unknown Institution"
        
        # Save all accounts
        with open(file_path, 'w') as f:
            json.dump({
                "last_updated": datetime.now().isoformat(),
                "accounts": all_accounts
            }, f, indent=2)
        
        logger.info(f"Saved {len(new_accounts)} new accounts for user {user_id}")
        logger.info(f"Total accounts: {len(all_accounts)}")

    def _convert_dates_to_strings(self, data: Any) -> Any:
        """Recursively convert all date objects to strings in a data structure"""
        if isinstance(data, (datetime, date)):
            return data.strftime('%Y-%m-%d')
        elif isinstance(data, dict):
            return {k: self._convert_dates_to_strings(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_dates_to_strings(item) for item in data]
        return data

    def save_transactions(self, user_id: str, transactions: List[Dict[str, Any]]) -> None:
        """Save transactions for a user"""
        temp_file_path = None
        try:
            # Convert all date objects to strings recursively
            transactions = self._convert_dates_to_strings(transactions)
            
            file_path = self._get_user_file(user_id, "transactions")
            # Write to a temporary file first
            temp_file_path = file_path + '.tmp'
            
            # Prepare data for JSON serialization
            data_to_save = {
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "transactions": transactions
            }
            
            with open(temp_file_path, 'w') as f:
                json.dump(data_to_save, f, indent=2)
            
            # If write was successful, rename temp file to actual file
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_file_path, file_path)
            
            logger.info(f"Saved {len(transactions)} transactions for user {user_id}")
        except Exception as e:
            logger.error(f"Error saving transactions: {str(e)}")
            # Clean up temp file if it exists
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise

    def get_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        """获取账户信息"""
        file_path = self._get_user_file(user_id, "accounts")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                data = json.load(f)
                accounts = data.get("accounts", [])
                # Ensure each account has an institution_name
                for account in accounts:
                    if "institution_name" not in account:
                        account["institution_name"] = "Unknown Institution"
                return accounts
        return []

    def get_transactions(self, user_id: str, start_date: date = None, end_date: date = None) -> List[Dict[str, Any]]:
        """Get transactions for a user within the specified date range"""
        try:
            file_path = self._get_user_file(user_id, "transactions")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    transactions = data.get("transactions", [])
                    
                    if not start_date or not end_date:
                        return transactions
                    
                    # Filter transactions by date range
                    filtered_transactions = []
                    for transaction in transactions:
                        try:
                            transaction_date = datetime.strptime(transaction['date'], '%Y-%m-%d').date()
                            if start_date <= transaction_date <= end_date:
                                filtered_transactions.append(transaction)
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Error parsing transaction date: {str(e)}")
                            continue
                    
                    return filtered_transactions
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Error reading transactions file: {str(e)}")
            # If file is corrupted, remove it
            if os.path.exists(file_path):
                os.remove(file_path)
            return []
        except Exception as e:
            logger.error(f"Unexpected error reading transactions: {str(e)}")
            return []

    def get_account_summary(self, user_id: str, start_date: date = None, end_date: date = None) -> Dict[str, Any]:
        """Get detailed account summary information for the specified date range"""
        try:
            accounts = self.get_accounts(user_id)
            transactions = self.get_transactions(user_id, start_date, end_date)
            
            # 1. Group accounts by financial institution
            institutions = {}
            for acc in accounts:
                # Get institution name from the account data
                institution_name = acc.get("institution_name", "Unknown Institution")
                if institution_name not in institutions:
                    institutions[institution_name] = {
                        "accounts": [],
                        "total_balance": 0.0,
                        "recent_transactions": []
                    }
                institutions[institution_name]["accounts"].append(acc)
                institutions[institution_name]["total_balance"] += float(acc.get("balances", {}).get("current", 0))
            
            # Log institution information for debugging
            logger.info("Institution Summary:")
            for inst_name, inst_data in institutions.items():
                logger.info(f"Institution: {inst_name}")
                logger.info(f"Number of accounts: {len(inst_data['accounts'])}")
                logger.info(f"Total balance: ${inst_data['total_balance']:.2f}")
                logger.info(f"Recent transactions: {len(inst_data['recent_transactions'])}")
                logger.info("---")
            
            # 2. Get transactions for each institution within the date range
            for institution in institutions.values():
                institution["recent_transactions"] = [
                    t for t in transactions 
                    if any(t.get("account_id") == acc.get("account_id") for acc in institution["accounts"])
                ]
            
            # 3. Group accounts by type and calculate totals
            account_types = {}
            for acc in accounts:
                acc_type = acc.get("type", "unknown")
                if acc_type not in account_types:
                    account_types[acc_type] = {
                        "accounts": [],
                        "total_balance": 0.0,
                        "recent_transactions": []
                    }
                account_types[acc_type]["accounts"].append(acc)
                account_types[acc_type]["total_balance"] += float(acc.get("balances", {}).get("current", 0))
                
                # Get transactions for this account type within the date range
                account_types[acc_type]["recent_transactions"] = [
                    t for t in transactions 
                    if any(t.get("account_id") == a.get("account_id") for a in account_types[acc_type]["accounts"])
                ]
            
            # 4. Group transactions by category
            categories = {}
            total_recent_transactions = 0
            
            for transaction in transactions:
                # Calculate total transactions
                total_recent_transactions += float(transaction.get("amount", 0))
                
                # Group by category
                category = transaction.get("category", ["Uncategorized"])[0]
                if category not in categories:
                    categories[category] = {
                        "transactions": [],
                        "total_amount": 0.0,
                        "count": 0
                    }
                categories[category]["transactions"].append(transaction)
                categories[category]["total_amount"] += float(transaction.get("amount", 0))
                categories[category]["count"] += 1
            
            # Calculate overall totals
            total_balance = sum(float(acc.get("balances", {}).get("current", 0)) for acc in accounts)

            return {
                "total_balance": total_balance,
                "total_recent_transactions": total_recent_transactions,
                "institutions": institutions,
                "account_types": account_types,
                "categories": categories,
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"Error getting summary: {str(e)}")
            raise

    def clean_test_data(self, user_id: str = None) -> None:
        """Clean out test data. If user_id is provided, only clean that user's data."""
        try:
            if user_id:
                # Clean specific user's data
                for data_type in ["accounts", "transactions"]:
                    file_path = self._get_user_file(user_id, data_type)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Removed {data_type} data for user {user_id}")
            else:
                # Clean all data
                for filename in os.listdir(self.storage_dir):
                    if filename.endswith('.json'):
                        file_path = os.path.join(self.storage_dir, filename)
                        os.remove(file_path)
                        logger.info(f"Removed {filename}")
        except Exception as e:
            logger.error(f"Error cleaning test data: {str(e)}")
            raise 