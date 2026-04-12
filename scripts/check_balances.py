
import os
from pathlib import Path
from stellar_sdk import Server
from dotenv import load_dotenv

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

def check_balances():
    horizon_url = os.getenv("HORIZON_URL", "https://horizon-testnet.stellar.org")
    server = Server(horizon_url)
    
    accounts = {
        "DEPLOYER": os.getenv("DEPLOYER_PUBLIC_KEY"),
        "EXECUTOR": os.getenv("EXECUTOR_PUBLIC_KEY")
    }
    
    print(f"Checking Stellar Testnet balances via: {horizon_url}\n")
    
    for name, pubkey in accounts.items():
        if not pubkey:
            print(f"{name}: Public key not found in .env")
            continue
            
        try:
            account = server.accounts().account_id(pubkey).call()
            balances = account.get("balances", [])
            print(f"--- {name} Wallet ---")
            print(f"Public Key: {pubkey}")
            for b in balances:
                asset_type = b.get("asset_type")
                balance = b.get("balance")
                if asset_type == "native":
                    print(f"Balance: {balance} XLM")
                else:
                    asset_code = b.get("asset_code")
                    print(f"Balance: {balance} {asset_code}")
            print()
        except Exception as e:
            print(f"--- {name} Wallet ---")
            print(f"Public Key: {pubkey}")
            print(f"Error fetching balance: {e} (Account might not be funded yet)\n")

if __name__ == "__main__":
    check_balances()
