import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from stellar_sdk import Keypair

# Project root (directory that contains `api/` and `scripts/`)
ROOT = Path(__file__).resolve().parent.parent


def generate_and_fund(name: str) -> tuple[str, str]:
    print(f"Generating keypair for {name}...")
    kp = Keypair.random()
    public_key = kp.public_key
    secret = kp.secret

    print(f"Funding {name} ({public_key}) via Friendbot...")
    try:
        r = httpx.get(
            f"https://friendbot.stellar.org/",
            params={"addr": public_key},
            timeout=30.0,
        )
        if r.status_code == 200:
            print(f"Successfully funded {name}.")
        else:
            print(f"Failed to fund {name}: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Error funding {name}: {e}")

    return public_key, secret


if __name__ == "__main__":
    env_path = ROOT / ".env"
    parent_env = ROOT.parent / ".env"
    load_dotenv(env_path)
    if parent_env.is_file():
        load_dotenv(parent_env, override=False)

    existing_registry = os.getenv("REGISTRY_CONTRACT_ID", "").strip()
    existing_gemini = os.getenv("GEMINI_API_KEY", "").strip()

    deployer_pub, deployer_sec = generate_and_fund("DEPLOYER")
    executor_pub, executor_sec = generate_and_fund("EXECUTOR")

    with open(env_path, "w", encoding="utf-8") as f:
        f.write("STELLAR_NETWORK=TESTNET\n")
        f.write("HORIZON_URL=https://horizon-testnet.stellar.org\n")
        f.write("SOROBAN_RPC_URL=https://soroban-testnet.stellar.org\n")
        f.write(f"DEPLOYER_PUBLIC_KEY={deployer_pub}\n")
        f.write(f"DEPLOYER_SECRET={deployer_sec}\n")
        f.write(f"EXECUTOR_PUBLIC_KEY={executor_pub}\n")
        f.write(f"EXECUTOR_SECRET={executor_sec}\n")
        f.write(f"REGISTRY_CONTRACT_ID={existing_registry}\n")
        f.write(f"GEMINI_API_KEY={existing_gemini}\n")

    print(f"\nWrote {env_path} with funded testnet accounts.")
    print("Next: deploy the Soroban registry (see README), set REGISTRY_CONTRACT_ID, then run registry_client.py.")
