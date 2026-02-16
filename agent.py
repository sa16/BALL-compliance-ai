import logging 
import json
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from typing import List, Literal, Optional
import os
import re
from sqlalchemy.orm import Session
from database import init_db_connection, SessionLocal
from retriever import retrieve_relevant_chunks
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

LLM_MODEL = "gpt-4o-mini"

#Pydantic contracts - first level of anti-hallucination measure
#LLM responses will stricly meet given contract labels
class ComplianceResponse(BaseModel):
    status: Literal["PASS", "FAIL", "AMBIGUOUS", "INCONCLUSIVE"] 
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    reasoning: str
    citations: List[str]

class ComplianceAgent:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("openai api key not found.")
        self.client = OpenAI(api_key=api_key)

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

        logger.info('---- Start of Context Assembly Audit log----')

        for i, (chunk,score) in enumerate(chunks):
            source_id = f'Source {i+1}'
            valid_sources.append(source_id)

            e_type = chunk.source_type.lower()

            if e_type in entity_counts:
                entity_counts[e_type] +=1
            
            meta= chunk.chunk_metadata or {} #will cause type error if we don't return an empty dict
            ref = meta.get('section') or meta.get('version') or "Unknown"

            source_header = f"[{source_id}: {chunk.source_type.upper()} - {ref}\n]"
            context_parts.append(f'{source_header}\n{chunk.text_content}\n')

        return "\n".join(context_parts), valid_sources, entity_counts
    
    def verify_citations(self, response: ComplianceResponse, valid_sources: List[str])->ComplianceResponse:
        clean_citations=[]
        valid_set = set(valid_sources)

        for cite in response.citations:
            match = re.search(r'source \d+', cite, re.IGNORECASE)
            if match:
                extracted_source = match.group(0)
                if extracted_source in valid_set:
                    clean_citations.append(cite)
                else:
                    logger.warning(f'Hallucination blocked: {cite} not in valid sources')
            else:
                logger.warning(f'Malformed citation blocked: {cite}')

        response.citations = clean_citations
        return response
    
    def analyze(self, query: str, session: Session)->dict:
        logger.info(f'retrieving evidence for query: {query}')
        chunks = retrieve_relevant_chunks(query, session)

        if not chunks:
            logger.warning("No evidence found (retriever returned 0)") 
            return self._build_inconclusive_response("No docs found.")
        
        #Circuit breaker logi: find a reg with no matching policy, do not audit

        context_text, valid_sources, entity_counts = self.assemble_context(chunks)
        if entity_counts["regulation"]==0:
            logger.warning("Circuit Break: Found 0 Regulations.")
            return self._build_inconclusive_response("No relevant regulations found to compare policy.")
        
        if entity_counts["policy"]==0:
            logger.warning("Circuit Break: Found 0 Polcies.")
            return self._build_inconclusive_response("No relevant policy found to audit ")
        
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
            response = self.client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content":system_prompt},
                    {"role": "user", "content":user_message}

                ],
                temperature=0.0,
                response_format={"type":"json_object"}
            )
            raw_content = response.choices[0].message.content
            try:
                data=json.loads(raw_content)
                structered_response = ComplianceResponse(**data)
                final_response = self.verify_citations(structered_response,valid_sources)
                return final_response.model_dump()
            
            except json.JSONDecodeError:
                logger.error(f'LLM returned Invalid JSON')
                return {"status":"error", "reason":"Model parsing failed"}
            except ValidationError as ve:
                logger.error(f'Pydantic validation failed: {ve}')
                return {"status":"error", "reason":"Model output schema Mismatch"}

        except Exception as e:
            logger.error(f'analysis failed: {e}')
            return {"status":"error", "reason":str(e)}


        
        
    def _build_inconclusive_response(self, reason: str):
        return ComplianceResponse(
            status="INCONCLUSIVE",
            reasoning=reason,
            confidence="LOW",
            citations=[]
        ).model_dump()
    
if __name__=="__main__":
    try: 
        init_db_connection()
    except Exception as e:
        logger.critical(f"failed to connect to DB {e}")
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
        logger.error(f"smoke test failed: {e}")
    finally:
        session.close()







    



    
        



        
        







