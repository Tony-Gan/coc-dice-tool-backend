import logging
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from routers.roll_router import router as roll_router
from datetime import datetime

# Setup logging
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s:%(levelname)s:%(message)s')

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse('static/index.html')

# Include the new dice router
app.include_router(roll_router, prefix="/dice")

# Function to log command history
def log_command_history(ip: str, command: str, args: list):
    with open('logs/command_history.txt', 'a') as f:
        f.write(f"{datetime.now()} - IP: {ip} - Command: {command} - Args: {args}\n")

@app.post("/dice/log_command")
async def log_command(request: Request):
    body = await request.json()
    ip = body.get('ip', '未知')
    command = body.get('command', '未知')
    args = [body.get('a1', ''), body.get('a2', ''), body.get('a3', ''), body.get('a4', ''), body.get('a5', ''), body.get('a6', '')]
    log_command_history(ip, command, args)
    return JSONResponse(content={"message": "Logged"}, status_code=200)
