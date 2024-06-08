import logging
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from routers.roll_router import router as roll_router

# Setup logging
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s:%(levelname)s:%(message)s')

app = FastAPI()

origins = [
    "http://8.219.207.170",  # Your actual IP address
    "http://8.219.207.170:80",  # If you specify port explicitly
    "http://8.219.207.170:3000",  # If your frontend runs on a specific port
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return RedirectResponse(url="/static/index.html")

# Include the new dice router
app.include_router(roll_router, prefix="/dice")
