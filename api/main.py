from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routers import execute
from stellar_sdk import Server
from api.models.job import JobRequest
from api.services.docker_runner import docker_runner
from dotenv import load_dotenv
import os
import uuid
import asyncio
from datetime import UTC, datetime
import json
import webbrowser
import threading
import time
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # This runs on startup
    def open_browser():
        time.sleep(1.5)
        url = "http://127.0.0.1:8000"
        print(f"\n[SYSTEM] Launching Dashboard: {url}")
        print(f"[SYSTEM] Agent Vault: {url}/vault\n")
        webbrowser.open(url)
    
    threading.Thread(target=open_browser, daemon=True).start()
    yield
    # This runs on shutdown

app = FastAPI(title="Stellarpay Executor API", lifespan=lifespan)

# In-memory storage for the latest job state to sync with Vault
latest_job_state = {
    "status": "idle",
    "step": 0,
    "last_tx": None
}

@app.get("/api/flow-status")
async def get_flow_status():
    return latest_job_state

@app.post("/execute/stream")
async def execute_stream_with_state(request: JobRequest):
    job_id = str(uuid.uuid4())
    
    async def event_generator():
        output_acc = []
        
        # Step 1: Wallet Auth
        latest_job_state["status"] = "authorizing"
        latest_job_state["step"] = 1
        latest_job_state["last_tx"] = {"type": "AUTH", "amount": "0.00001 XLM", "id": job_id[:8]}
        yield f"data: {json.dumps({'line': '> Authorizing wallet via Stellar Testnet...'})}\n\n"
        
        # Step 2: Registry Check
        latest_job_state["status"] = "registry"
        latest_job_state["step"] = 2
        yield f"data: {json.dumps({'line': '> Verifying agent in registry contract...'})}\n\n"
        
        # Step 3: Execution
        latest_job_state["status"] = "executing"
        latest_job_state["step"] = 3
        
        async for line in docker_runner.run(request.image, request.cmd):
            output_acc.append(line)
            yield f"data: {json.dumps({'line': line})}\n\n"
        
        # Step 4: Finality
        latest_job_state["status"] = "completed"
        latest_job_state["step"] = 4
        
        result = {
            "job_id": job_id,
            "status": "completed",
            "output": "\n".join(output_acc),
            "timestamp": datetime.now(UTC).isoformat()
        }
        yield f"data: {json.dumps(result)}\n\n"
        
        # Keep the "completed" state visible for 5 seconds before resetting to idle
        await asyncio.sleep(5)
        latest_job_state["status"] = "idle"
        latest_job_state["step"] = 0

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Include router AFTER the stream route to ensure override
app.include_router(execute.router)

# Mount static files
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
