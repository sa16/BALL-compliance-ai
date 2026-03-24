import logging
from typing import List
from fastapi import Depends, APIRouter, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import InternalPolicy, RequestMetric, Users
from app.schemas.audit import PolicyItem, ComplianceResponse, AuditRequest
from app.services.telemetry import TelemetryService
from app.db.session import SessionLocal
import uuid
from typing import Optional
from sqlalchemy.exc import SQLAlchemyError
from app.api.auth import require_role

# logger = logging.getLogger("API")
logger = logging.getLogger("json_logger")

router = APIRouter()

def save_metrics_background(intent: str, status_code: int, endpoint: str, telemetry: TelemetryService,user_id: Optional[str] = None):
    """
    -runs in bg to collect metrics
    -creates own db session to avoid race condition with fastAPI request loop
    """

    db = SessionLocal()
    try:
        data = telemetry.get_summary()
        metric = RequestMetric(
            request_id=data["request_id"],
            endpoint=endpoint,
            user_id = user_id,
            intent=intent,
            status_code=status_code,
            error_type=data.get("error_type"),
            total_latency_ms=data["total_latency_ms"],
            routing_latency_ms=data["routing_ms"],
            retrieval_latency_ms=data["retrieval_ms"],
            llm_latency_ms=data["llm_ms"],
            prompt_tokens=data["prompt_tokens"],
            completion_tokens=data["completion_tokens"],
            total_tokens=data["prompt_tokens"] + data["completion_tokens"],
            cost_usd=data["cost_usd"],
            model_name=data["model_str"]
        )
        
        for attempt in range(2):
            try:
                db.add(metric)
                db.commit()
                logger.info({
                    "event": "metrics_persisted", 
                    "request_id": telemetry.request_id,
                    "user_id": user_id,
                    "cost_usd": data["cost_usd"],
                    "total_latency_ms": data["total_latency_ms"]
                })
                break
            except SQLAlchemyError as db_err:
                db.rollback()
                if attempt == 1: # Log only if the final attempt fails
                    logger.error({
                        "event": "metrics_save_failed", 
                        "error": str(db_err), 
                        "request_id": telemetry.request_id
                    })
        # logger.info({
        #     "event": "metrics_persisted", 
        #     "request_id": telemetry.request_id, 
        #     "cost_usd": data["cost_usd"],
        #     "total_latency_ms": data["total_latency_ms"]
        # })
    except Exception as e:
        logger.error({"event": "metrics_save_failed", "error": type(e).__name__}) 
    finally:
        db.close()     




@router.get("/policies", response_model=List[PolicyItem])
def list_policies(db: Session = Depends(get_db), current_user: Users = Depends(require_role("auditor"))):
    db: Session = Depends(get_db),
    try:
        policies = db.query(InternalPolicy).all() #not optimal, this is for mvp only
        return [{"id":str(p.id), "name": str(p.name)} for p in policies]
    except Exception as e:
        logger.error({"event": "policy_list_error", "error": type(e).__name__})
        raise HTTPException(status_code=500, detail="Internal Error")
    
@router.post("/audit", response_model=ComplianceResponse)
def run_audit(request:AuditRequest, request_ctx: Request,background_tasks: BackgroundTasks,current_user: Users = Depends(require_role("auditor")),db: Session = Depends(get_db)):
    req_id = str(uuid.uuid4())
    telemetry = TelemetryService(request_id=req_id)
    logger.info({
        "event": "audit_request_start", 
        "request_id": req_id, 
        "query_length": len(request.query)
    })
    try:
        agent = request_ctx.app.state.agent # agent = ComplianceAgent() would load agent to memory at every POST, that's not optimal

        result = agent.analyze(
            query=request.query,
            session=db,
            policy_filter_id = request.policy_id,
            telemetry= telemetry
        )
        intent = result.get("intent", "UNKNOWN")
        background_tasks.add_task(
            save_metrics_background,
            intent=intent,
            telemetry=telemetry,
            status_code=200,
            endpoint="/audit",
            user_id=str(current_user.id)
        )

        return result
    except Exception as e:
            logger.error({"event": "audit_route_error", "request_id": req_id, "error": type(e).__name__})
        
            # Even on severe route failure, try to save what metrics we collected
            background_tasks.add_task(
                save_metrics_background, 
                telemetry=telemetry, 
                intent="ERROR", 
                status_code=500, 
                endpoint="/audit",
                user_id = str(current_user.id)
            )
            raise HTTPException(status_code=500, detail="Internal Error")
    


