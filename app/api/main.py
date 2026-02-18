import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.session import init_db_connection
from app.api.routes import router as api_router
from app.services.compliance_agent import ComplianceAgent
from app.api.routes import router as api_router

logger = logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("API")

@asynccontextmanager
async def  lifespan(app: FastAPI):
    try:
        init_db_connection()
        logger.info("Connected to DB Succesfully")
    except Exception as e:
        logger.critical(f"DB connection FAILED: {e}")
    
    try:
        app.state.agent = ComplianceAgent()
        logger.info("Compliance Agent Initialized")
    except Exception as e:
        logger.critical(f"failed to initialize agent: {e}")

    yield

    logger.info("Shutting down")

app= FastAPI(
        title="BALL Compliance Engine",
        description="Regulatory Gap Detection Microservice",
        version="1.0.0",
        lifespan=lifespan
    )
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if __name__=="__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)



