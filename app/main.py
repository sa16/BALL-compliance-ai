import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db.session import init_db_connection
from app.api.routes import router as api_router
from app.api.auth import router as auth_router
from app.services.compliance_agent import ComplianceAgent
from dotenv import load_dotenv


# logger = logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
# logger = logging.getLogger("API")
load_dotenv(override=True)
logger = logging.getLogger("json_logger")

@asynccontextmanager
async def  lifespan(app: FastAPI):
    try:
        init_db_connection()
        logger.info({"event": "db_connected"})
    except Exception as e:
        logger.critical({"event": "db_connection_failed", "error": str(e)})
    
    try:
        app.state.agent = ComplianceAgent()
        logger.info({"event": "agent_initialized"})
    except Exception as e:
        logger.critical({"event": "agent_initialization_failed", "error": str(e)})

    yield

    logger.info({"event": "shutting_down"})

app= FastAPI(
        title="BALL Compliance Engine",
        description="Regulatory Gap Detection Microservice",
        version="1.0.0",
        lifespan=lifespan
    )
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["http://localhost:5173", "http://localhost", "https://bal-compliance-ai.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(auth_router)

if __name__=="__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)



