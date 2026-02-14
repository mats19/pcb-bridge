from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import uvicorn

app = FastAPI(title="pcb-bridge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/status")
async def get_status():
    return {"status": "pcb-bridge is running"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
