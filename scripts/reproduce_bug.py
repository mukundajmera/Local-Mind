import asyncio
import time
from fastapi import FastAPI, BackgroundTasks

app = FastAPI()

# Mimic the bug: Async background task doing Sync CPU work
async def _process_upload_background_SIMULATED():
    print("Background task started - Blocking Loop")
    # Simulate tiktoken encoding (CPU bound)
    # This Sleep is blocking because it's time.sleep(), NOT asyncio.sleep()
    time.sleep(5) 
    print("Background task finished")

@app.post("/upload")
async def upload(background_tasks: BackgroundTasks):
    background_tasks.add_task(_process_upload_background_SIMULATED)
    return {"status": "accepted"}

@app.get("/status")
async def status():
    return {"status": "alive"}

# To verify:
# 1. Run this server: uvicorn reproduce_bug:app
# 2. Curl /upload
# 3. Immediately Curl /status -> It will hang for 5 seconds (FAIL)
