import logging 
import json
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from typing import List, Literal, Optional
import os
import re
from sqlalchemy.orm import Session
from app.db.session import init_db_connection, SessionLocal
from app.services.retriever import retrieve_balanced_chunks
from dotenv import load_dotenv
from functools import lru_cache
from app.services.telemetry import TelemetryService
from collections import OrderedDict
from contextlib import nullcontext

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
# logger = logging.getLogger(__name__)
logger = logging.getLogger("json_logger")
LLM_MODEL = "gpt-4o-mini"
BANK_NAME = os.getenv("BANK NAME", "BAL")

#Pydantic contracts - first level of anti-hallucination measure
#LLM responses will stricly meet given contract labels
class ComplianceResponse(BaseModel):
    status: Literal["PASS", "FAIL", "AMBIGUOUS", "INCONCLUSIVE"] 
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    reasoning: str
    citations: List[str]
    intent: str = "UNKNOWN"

class IntentResponse(BaseModel):
    category: Literal["COMPLIANCE_AUDIT", "SYSTEM_METADATA", "REJECT"]

# @lru_cache(maxsize=512)
# def _cache_intent_classification(query: str, api_key: str, telemetry:Optional[TelemetryService]=None)->str:
#     client = OpenAI(api_key=api_key)
#     with telemetry.measure("routing"):
#         system_prompt="""
#                         You are a Query Router for a Banking Compliance AI.
#                         Classify the user query into exactly one category:
#                         1. COMPLIANCE_AUDIT: Questions comparing internal policies to regulations.
#                         2. SYSTEM_METADATA: Questions asking "What is the bank's name?", "Who are you?".
#                         3. REJECT: Questions unrelated to banking/compliance (weather, jokes).
#                         OUTPUT JSON: {"category": "COMPLIANCE_AUDIT" | "SYSTEM_METADATA" | "REJECT"}
#                         """
#         try:
#             response= client.chat.completions.create(
#                 model=LLM_MODEL,
#                 messages=[{"role": "system", "content": system_prompt},
#                         {"role": "user", "content": query}],
#                 temperature=0.0,
#                 max_tokens=50,
#                 response_format={"type":"json_object"}
#                 )
#             telemetry.track_llm(response.usage, LLM_MODEL)
#             data = json.loads(response.choices[0].message.content)
#             return intentResponse(**data).category
#         except Exception:
#             logger.error({"event": "intent_classification_failed", "error": str(e)})
#             telemetry.set_error("INTENT_FAILURE")
#             return "ERROR"
        
class ComplianceAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("openai api key not found.")
        self.client = OpenAI(api_key=self.api_key)
        #replacing initial LRU cache approach
        self._intent_cache = OrderedDict() 
        self._cache_max_size = 1000


        
    def classify_intent(self, query: str, telemetry: Optional[TelemetryService]=None)->str:
        if query in self._intent_cache:
            self._intent_cache.move_to_end(query)
            return self._intent_cache[query]
        cm = telemetry.measure("routing") if telemetry else nullcontext()
        with cm:
            system_prompt="""
                            You are a Query Router for a Banking Compliance AI.
                            Classify the user query into exactly one category:
                            1. COMPLIANCE_AUDIT: Questions comparing internal policies to regulations.
                            2. SYSTEM_METADATA: Questions asking "What is the bank's name?", "Who are you?".
                            3. REJECT: Questions unrelated to banking/compliance (weather, jokes).
                            OUTPUT JSON: {"category": "COMPLIANCE_AUDIT" | "SYSTEM_METADATA" | "REJECT"}
                            """
            try:
                response= self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[{"role": "system", "content": system_prompt},
                            {"role": "user", "content": query}],
                    temperature=0.0,
                    max_tokens=50,
                    response_format={"type":"json_object"},
                    timeout=5.0
                    )
                telemetry.track_llm(response.usage, LLM_MODEL)
                data = json.loads(response.choices[0].message.content)
                intent = IntentResponse(**data).category

                self._intent_cache[query]=intent
                if len(self._intent_cache)>self._cache_max_size:
                    self._intent_cache.popitem(last=False)
                return intent
                    
            except Exception as e:
                logger.error({"event": "intent_classification_failed", "error": str(e)})
                if telemetry: telemetry.set_error("INTENT_FAILURE")
                return "REJECT"

        

    def assemble_context(self,chunks: List)->tuple[str, List[str],dict]:
        """
        formats/matches raw chunks into labels:

        returns:
        - formated text
        -list of sources
        -# of regulations & # of policies (regs & no policy could be a case of hallucination)
        """

        context_parts=[]
        valid_sources=[]
        entity_counts={"regulation":0, "policy":0}

        # logger.info('---- Start of Context Assembly Audit log----')
        logger.info({"event":"context_assembly_start"})

        for i, (chunk,score) in enumerate(chunks):
            source_id = f'Source {i+1}'
            valid_sources.append(source_id)

            e_type = chunk.source_type.lower()

            if e_type in entity_counts:
                entity_counts[e_type] +=1
            
            meta= chunk.chunk_metadata or {} #will cause type error if we don't return an empty dict
            ref = meta.get('section') or meta.get('version') or "Unknown"

            source_header = f"[{source_id}: {chunk.source_type.upper()} - {ref}]"

            #logging the mapping
            # logger.info(f"  mapped {source_id}: {chunk.source_type.upper()} ({ref}) [Score: {score:.2f}]")
            logger.info({
                "event":"source_mapped",
                "source_id":source_id,
                "type":ref,
                "score":round(score, 2)
                })

            context_parts.append(f'{source_header}\n{chunk.text_content}\n')

        return "\n".join(context_parts), valid_sources, entity_counts
    
    def verify_citations(self, response: ComplianceResponse, valid_sources: List[str])->ComplianceResponse:
        clean_citations=[]
        valid_set = set(valid_sources)

        for cite in response.citations:
            match = re.search(r'source \d+', cite, re.IGNORECASE)
            if match:
                extracted_source = match.group(0).title()
                if extracted_source in valid_set:
                    clean_citations.append(cite)
                else:
                    # logger.warning(f'Hallucination blocked: {cite} not in valid sources')
                    logger.warning({"event":"hallucination_blocked", "citation":cite})
            else:
                logger.warning({"event":"Malformed_citation_blocked", "citation": cite})

        response.citations = clean_citations
        return response
    
    def analyze(self, query: str, session: Session, policy_filter_id: str = None, telemetry: Optional[TelemetryService]=None)->dict:

        intent = self.classify_intent(query, telemetry)
        logger.info({"event": "intent_classified", "intent": intent})

        # 2. HANDLE FAST PATHS
        if intent == "REJECT":
            return self._build_inconclusive_response(
                "This query appears unrelated to banking compliance. Access denied.", intent
            )
        
        if intent == "SYSTEM_METADATA":
            return ComplianceResponse(
                status="PASS",
                confidence="HIGH",
                reasoning=f"I am the {BANK_NAME} Compliance Engine.",
                citations=[],
                intent=intent
            ).model_dump()
        
        # logger.info(f'retrieving evidence for query: {query} (filter: {policy_filter_id})')
        logger.info({"event": "retrieval_start", "query": query, "policy_filter_id": policy_filter_id})
        #cost measure for retrieval
        cm_retrieval = telemetry.measure("retrieval") if telemetry else nullcontext()
        with cm_retrieval:
            chunks = retrieve_balanced_chunks(query, session, policy_filter_id=policy_filter_id, telemetry=telemetry)

        if not chunks:
            # logger.warning("No evidence found (retriever returned 0)") 
            logger.warning({"event": "circuit_break_empty_retrieval"}) 
            if telemetry: telemetry.set_error("RETRIEVAL_EMPTY")
            return self._build_inconclusive_response("No docs found.", intent)
        
        #Circuit breaker logi: find a reg with no matching policy, do not audit

        context_text, valid_sources, entity_counts = self.assemble_context(chunks)
        if entity_counts["regulation"]==0:
            # logger.warning("Circuit Break: Found 0 Regulations.")
            logger.warning({"event": "circuit_break_no_regs"}) 
            if telemetry: telemetry.set_error("RETRIEVAL_MISSING_REGS")
            return self._build_inconclusive_response("No relevant regulations found to compare policy.", intent)
        
        if entity_counts["policy"]==0:
            # logger.warning("Circuit Break: Found 0 Polcies.")
            logger.warning({"event": "circuit_break_no_policy"}) 
            if telemetry: telemetry.set_error("RETRIEVAL_MISSING_POLICY")
            return self._build_inconclusive_response("No relevant policy found to audit ", intent)
        
        system_prompt="""
                    Your are senior compliance officer for a tier-1 bank. Audit Internal policies against Regulatory obligations.

                    INSTRUCTIONS:
                    -Compare Policies vs Regulations
                    -Mark PASS if fully compliant
                    -Mark FAIL if a specific requirement is missing or contradicted
                    -Mark AMBIGUOUS if language is vague
                    -MARK INCONCLUSIVE if the retrieved context lacks sufficient info
                    -Cite specific sources numbers(eg. source 1) for every claim
                    -IGNORE external knowledge. Use only provided sources

                    OUTPUT JSON SCHEMA:
                                    {
                                        "status": "PASS" | "FAIL" | "AMBIGUOUS" | "INCONCLUSIVE",
                                        "confidence": "HIGH" | "MEDIUM" | "LOW",
                                        "reasoning": "Explanation...",
                                        "citations": ["Source 1", "Source 2"]
                                    }


                      """
        user_message = f'QUERY: {query}\n\n--- sources ---\n{context_text}'

        try:
            logger.info("Sending info to LLM")
            logger.info({"event":"llm_analysis_start"})
            cm_llm = telemetry.measure("llm") if telemetry else nullcontext()
            with cm_llm:
                response = self.client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        {"role": "system", "content":system_prompt},
                        {"role": "user", "content":user_message}

                    ],
                    temperature=0.0,
                    response_format={"type":"json_object"},
                    timeout=20.0
                )
            if telemetry:
                telemetry.track_llm(response.usage, LLM_MODEL)

            raw_content = response.choices[0].message.content
            try:
                data=json.loads(raw_content)
                data['intent']=intent
                structured_response = ComplianceResponse(**data)
                final_response = self.verify_citations(structured_response,valid_sources)
                return final_response.model_dump()
            
            except json.JSONDecodeError:
                logger.error({"event": "llm_invalid_json"})
                if telemetry: telemetry.set_error("LLM_JSON_ERROR")
                return {"status":"error", "reason":"Model parsing failed"}
            except ValidationError as ve:
                logger.error({"event": "pydantic_validation_failed", "error": str(ve)})
                if telemetry: telemetry.set_error("LLM_VALIDATION_ERROR")
                return {"status":"error", "reason":"Model output schema Mismatch"}

        except Exception as e:
            logger.error({"event": "analysis_failed", "error": str(e)})
            if telemetry: telemetry.set_error("LLM_API_ERROR")
            return {"status":"error", "reason":str(e)}


        
        
    def _build_inconclusive_response(self, reason: str, intent: str = "UNKNOWN")->ComplianceResponse:
        return ComplianceResponse(
            status="INCONCLUSIVE",
            reasoning=reason,
            confidence="LOW",
            citations=[],
            intent= intent
        ).model_dump()
    
    def _build_error_response(self, reason: str, intent: str = "UNKNOWN")->ComplianceResponse:
        return ComplianceResponse(
            status="INCONCLUSIVE",
            reasoning=reason,
            confidence="LOW",
            citations=[],
            intent= intent
            
        ).model_dump()
    
if __name__=="__main__":
    try: 
        init_db_connection()
    except Exception as e:
        logger.critical({"event": "db_connection_failed", "error": str(e)})
    try:
        session = SessionLocal()
        agent= ComplianceAgent()
     #Smoke test

        query ="Does the bank have adequate exit strategies for vendors?"

        result=agent.analyze(query, session)

        print("\n" + "="*50)
        print("Hardened Compliance Report")
        print("="*50)
        print(json.dumps(result, indent=4))
        print("="*50+"\n")

    except Exception as e:
       logger.critical({"event": "smoke_test_failed", "error": str(e)})
    finally:
        session.close()







    



    
        



        
        







