import logging
from typing import List
from fastapi import Depends, APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import InternalPolicy
from app.schemas.audit import PolicyItem, ComplianceResponse, AuditRequest

logger = logging.getLogger("API")

router = APIRouter()

@router.get("/policies", response_model=List[PolicyItem])
def list_policies(db: Session = Depends(get_db)):
    try:
        policies = db.query(InternalPolicy).all() #not optimal, this is for mvp only
        return [{"id":str(p.id), "name": str(p.name)} for p in policies]
    except Exception as e:
        logger.error(f"Failed to list polices: {e}")
        raise HTTPException(status_code=500, detail="Internal Error")
    
@router.post("/audit", response_model=ComplianceResponse)
def run_audit(request:AuditRequest, request_ctx: Request,db: Session = Depends(get_db)):
    try:
        agent = request_ctx.app.state.agent # agent = ComplianceAgent() would load agent to memory at every POST, that's not optimal

        result = agent.analyze(
            query=request.query,
            session=db,
            policy_filter_id = request.policy_id
        )

        return result
    except Exception as e:
        logger.error(f"Audit process failed: {e}")
        raise HTTPException(status_code=500, detail="Internal Error")
    


