
import os
from pathlib import Path
from dotenv import load_dotenv
from registry_client import RegistryClient

# Inner project .env then parent folder .env
_root = Path(__file__).resolve().parent.parent
_parent_env = _root.parent / ".env"
if (_root / ".env").is_file():
    load_dotenv(_root / ".env")
if _parent_env.is_file():
    load_dotenv(_parent_env, override=True)

def test_get_agent():
    client = RegistryClient()
    print(f"Testing get_agent for contract: {client.contract_id}")
    try:
        # Just try to call get_agent for a non-existent agent to see if it fails with 'contract not found' or similar
        client.get_agent("test-agent")
        print("get_agent call simulated successfully.")
    except Exception as e:
        print(f"get_agent call failed: {e}")

if __name__ == "__main__":
    test_get_agent()
