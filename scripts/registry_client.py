import os
import time
from pathlib import Path
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, SorobanServer, scval
from stellar_sdk.soroban_rpc import GetTransactionStatus, SendTransactionStatus
from dotenv import load_dotenv

# Inner project .env then parent folder .env (parent often holds real keys in this repo layout).
_root = Path(__file__).resolve().parent.parent
_parent_env = _root.parent / ".env"
if (_root / ".env").is_file():
    load_dotenv(_root / ".env")
if _parent_env.is_file():
    load_dotenv(_parent_env, override=True)

class RegistryClient:
    def __init__(self):
        self.rpc_server_url = os.getenv("SOROBAN_RPC_URL", "https://soroban-testnet.stellar.org")
        self.horizon_url = os.getenv("HORIZON_URL", "https://horizon-testnet.stellar.org")
        self.network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
        _cid = (os.getenv("REGISTRY_CONTRACT_ID") or "").strip()
        self.contract_id = _cid or None

        self.soroban_server = SorobanServer(self.rpc_server_url)
        self.server = Server(self.horizon_url)

    def _submit_tx(self, transaction, secret_key):
        kp = Keypair.from_secret(secret_key)
        transaction.sign(kp)

        send_response = self.soroban_server.send_transaction(transaction)
        if send_response.status not in (
            SendTransactionStatus.PENDING,
            SendTransactionStatus.DUPLICATE,
        ):
            raise Exception(
                f"Send transaction failed: {send_response.status} "
                f"{send_response.error_result_xdr}"
            )

        tx_hash = send_response.hash
        print(f"Transaction submitted: {tx_hash}")

        while True:
            get_response = self.soroban_server.get_transaction(tx_hash)
            if get_response.status == GetTransactionStatus.NOT_FOUND:
                time.sleep(2)
                continue
            if get_response.status == GetTransactionStatus.SUCCESS:
                return get_response
            if get_response.status == GetTransactionStatus.FAILED:
                raise Exception(f"Transaction failed: {get_response.result_xdr}")
            time.sleep(2)

    def register_agent(self, agent_id: str, metadata_cid: str, secret_key: str):
        if not self.contract_id:
            raise ValueError("Set REGISTRY_CONTRACT_ID in .env (deploy registry contract first).")
        kp = Keypair.from_secret(secret_key)
        source_account = self.soroban_server.load_account(kp.public_key)

        args = [
            scval.to_address(kp.public_key),
            scval.to_string(agent_id),
            scval.to_string(metadata_cid),
        ]

        tx = (
            TransactionBuilder(source_account, self.network_passphrase)
            .append_invoke_contract_function_op(
                self.contract_id, "register_agent", args
            )
            .set_timeout(30)
            .build()
        )

        tx = self.soroban_server.prepare_transaction(tx)
        return self._submit_tx(tx, secret_key)

    def get_agent(self, agent_id: str):
        if not self.contract_id:
            raise ValueError("Set REGISTRY_CONTRACT_ID in .env (deploy registry contract first).")
        secret = os.getenv("DEPLOYER_SECRET")
        if not secret or not secret.strip():
            raise ValueError("Set DEPLOYER_SECRET in .env for read-only simulations.")

        args = [scval.to_string(agent_id)]

        source_kp = Keypair.from_secret(secret)
        source_account = self.soroban_server.load_account(source_kp.public_key)

        tx = (
            TransactionBuilder(source_account, self.network_passphrase)
            .append_invoke_contract_function_op(self.contract_id, "get_agent", args)
            .set_timeout(30)
            .build()
        )

        simulate_response = self.soroban_server.simulate_transaction(tx)
        if simulate_response.error:
            raise Exception(f"Simulation failed: {simulate_response.error}")

        if not simulate_response.results:
            return None

        result_val = simulate_response.results[0].xdr
        return result_val

if __name__ == "__main__":
    client = RegistryClient()
    print(f"Registry Client initialized for contract: {client.contract_id!r}")
    try:
        health = client.soroban_server.get_health()
        print(f"Soroban RPC health: {health}")
    except Exception as e:
        print(f"Soroban RPC health check failed: {e}")
    # Example usage:
    # client.register_agent("agent-xyz", "Qm...", os.getenv("DEPLOYER_SECRET"))
