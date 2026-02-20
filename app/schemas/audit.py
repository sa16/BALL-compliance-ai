from pydantic import BaseModel
from typing import List, Optional, Literal


#The Request Contract

class AuditRequest(BaseModel):
    query: str
    policy_id: Optional[str]= None

class ComplianceResponse(BaseModel):
    status: Literal["PASS", "FAIL", "AMBIGUOUS", "INCONCLUSIVE"] 
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    reasoning: str
    citations: List[str]
    intent: str = "UNKNOWN"

class PolicyItem(BaseModel):
    id: str
    name: str



