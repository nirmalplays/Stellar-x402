from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from api.models.job import JobRequest, JobResult, JobStatus
from api.services.docker_runner import docker_runner
import uuid
import asyncio
from datetime import UTC, datetime
import json
import os

router = APIRouter(prefix="/execute", tags=["execution"])

# Shared state for the Vault UI
latest_job_state = {
    "status": "idle",
    "step": 0,
    "last_tx": None
}

@router.get("/status")
async def get_flow_status():
    return latest_job_state

@router.post("/stream")
async def execute_stream(request: JobRequest):
    job_id = str(uuid.uuid4())
    
    async def event_generator():
        output_acc = []
        
        # Step 1: Wallet Auth
        latest_job_state["status"] = "authorizing"
        latest_job_state["step"] = 1
        latest_job_state["last_tx"] = {
            "type": "AUTH", 
            "amount": "0.00001 XLM", 
            "id": job_id[:8]
        }
        yield f"data: {json.dumps({'line': '> Authorizing wallet via Stellar Testnet...'})}\n\n"
        await asyncio.sleep(1) # Small delay for visual effect
        
        # Step 2: Registry Check
        latest_job_state["status"] = "registry"
        latest_job_state["step"] = 2
        yield f"data: {json.dumps({'line': '> Verifying agent in registry contract...'})}\n\n"
        
        # Actual registry simulation/check logic could go here
        # For now we simulate the check delay
        await asyncio.sleep(1)
        
        # Step 3: Execution
        latest_job_state["status"] = "executing"
        latest_job_state["step"] = 3
        
        async for line in docker_runner.run(request.image, request.cmd):
            output_acc.append(line)
            yield f"data: {json.dumps({'line': line})}\n\n"
        
        # Step 4: Finality
        latest_job_state["status"] = "completed"
        latest_job_state["step"] = 4
        
        result = JobResult(
            job_id=job_id,
            status=JobStatus.COMPLETED,
            output="\n".join(output_acc),
            timestamp=datetime.now(UTC).isoformat()
        )
        yield f"data: {result.model_dump_json()}\n\n"
        
        # Keep the "completed" state visible for a few seconds before resetting
        await asyncio.sleep(5)
        latest_job_state["status"] = "idle"
        latest_job_state["step"] = 0

    return StreamingResponse(event_generator(), media_type="text/event-stream")
