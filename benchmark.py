import logging
import json
import time
from sqlalchemy.orm import Session
from database import init_db_connection, SessionLocal
from agent import ComplianceAgent

# Configure simple logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("BENCHMARK")

def run_benchmark():
    try:
        init_db_connection()
    except Exception as e:
        logger.critical(f'failed to connect to db: {e}')
        return
    try:

        session = SessionLocal()
        agent = ComplianceAgent()

        test_cases = [
            {
                "name": "TEST 1: CLEAR PASS (Policy A vs OSFI)",
                "query": "Does the bank have documented exit strategies defined?",
                "expected": "PASS"
            },
            {
                "name": "TEST 2: CLEAR FAIL (Policy C Gap)",
                # Policy C is about 'Rapid Onboarding' and explicitly says continuity planning is NOT required.
                "query": "Does the Rapid Vendor Onboarding Pilot require long-term continuity planning?",
                "expected": "FAIL" 
            },
            {
                "name": "TEST 3: AMBIGUOUS (Policy B Vague)",
                # Policy B says "reasonable efforts" but no specific triggers.
                "query": "Does the Technology Procurement Guideline specify exact service level failure triggers?",
                "expected": "AMBIGUOUS" # or FAIL depending on LLM strictness
            },
            {
                "name": "TEST 4: CIRCUIT BREAKER (Policy Only)",
                # Searching for a specific internal budget that OSFI doesn't care about.
                # Likely to retrieve only Policy chunks.
                "query": "What is the budget limit for the Rapid Vendor Onboarding Pilot?",
                "expected": "INCONCLUSIVE" 
            },
            {
                "name": "TEST 5: CIRCUIT BREAKER (Regulation Only)",
                # Searching for a specific OSFI definition not in our policies.
                "query": "What is the definition of a FRFI according to OSFI B-10?",
                "expected": "INCONCLUSIVE"
            }
        ]

        print("\n STARTING COMPLIANCE BENCHMARK SUITE\n")

        for test in test_cases:
            print(f"Running: {test['name']}")
            print(f"Query: {test['query']}")

            #agent
            start_time = time.time()
            result = agent.analyze(test['query'],session)
            duration = time.time() - start_time

            status = result.get("status", "ERROR")
            citations = result.get("citations", [])



            if status == test['expected']:
                print(f"   RESULT: {status} (Matches Expected) | Time: {duration:.2f}s")
            elif test['expected'] in ["AMBIGUOUS", "FAIL"] and status in ["AMBIGUOUS", "FAIL"]:
                print(f"    RESULT: {status} (Acceptable Variance) | Time: {duration:.2f}s")
            else:
                print(f"    RESULT: {status} (Expected {test['expected']})")

            print(f"    Citations: {citations}")
            print(f"    Reasoning Snippet: {result.get('reasoning', '')[:100]}...")
            print("-" * 60 + "\n")

 
    except Exception as e:
        logger.error(f'benchmark failed: {e}')
    finally:
        session.close()

if __name__ =="__main__":
    run_benchmark()
