from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routers import execute
from stellar_sdk import Server
from dotenv import load_dotenv
import os
import webbrowser
import threading
import time
from contextlib import asynccontextmanager

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-open browser on startup
    def open_browser():
        time.sleep(1.5)
        url = "http://127.0.0.1:8000"
        print(f"\n[SYSTEM] Launching Dashboard: {url}")
        print(f"[SYSTEM] Agent Vault: {url}/vault\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
    
    threading.Thread(target=open_browser, daemon=True).start()
    yield

app = FastAPI(title="Stellarpay Executor API", lifespan=lifespan)

# Main Execution Router
app.include_router(execute.router)

# Mount static files for the dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/api/vault")
async def get_vault_data():
    horizon_url = os.getenv("HORIZON_URL", "https://horizon-testnet.stellar.org")
    server = Server(horizon_url)
    
    deployer_pk = os.getenv("DEPLOYER_PUBLIC_KEY")
    executor_pk = os.getenv("EXECUTOR_PUBLIC_KEY")
    
    data = {"wallets": [], "transactions": []}
    
    for name, pk in [("Deployer", deployer_pk), ("Executor", executor_pk)]:
        if not pk: continue
        try:
            acc = server.accounts().account_id(pk).call()
            balance = next((b["balance"] for b in acc["balances"] if b["asset_type"] == "native"), "0")
            data["wallets"].append({"name": name, "public_key": pk, "balance": balance})
            
            # Get last 5 transactions
            txs = server.transactions().for_account(pk).limit(5).order(desc=True).call()
            for tx in txs["_embedded"]["records"]:
                data["transactions"].append({
                    "account": name,
                    "hash": tx["hash"][:8] + "...",
                    "created_at": tx["created_at"],
                    "fee": f"{int(tx['fee_charged']) / 10000000} XLM",
                    "success": tx["successful"]
                })
        except Exception as e:
            print(f"Error fetching {name}: {e}")
            
    return data

@app.get("/")
async def root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"status": "ok", "project": "Stellarpay"}

@app.get("/vault")
async def vault_page():
    vault_file = os.path.join(static_dir, "vault.html")
    if os.path.exists(vault_file):
        return FileResponse(vault_file)
    raise HTTPException(status_code=404, detail="Vault page not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
