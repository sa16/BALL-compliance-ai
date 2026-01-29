import sys
import os
import logging
from database import init_db_connection, SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import Regulation, InternalPolicy

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

logger = logging.getLogger(__name__)

#expected paths & formats for file names, sections & versions

DATA_DIR_REGULATIONS = "data/regulations"
DATA_DIR_POLICIES = "data/internal_policies"

DEFAULT_REGULATION_SECTION = "2.3.5"
DEFAULT_POLICY_VERSION = "V1"

def ingest_regulations(session: Session, directory) -> int:
    """
    reads regulations files & stages them for db commit
    returns head count of succesfully staged valid files

    """
    #valid file path check
    if not os.path.exists(directory):
        logger.warning(f'directory not found: {directory}')
        return 0
    
    files_processed=0

    files = sorted([f for f in os.listdir(directory) if f.endswith('.txt')]) #sorting list of files, to ensure same order in case of re-runs

    for filename in files:
        try:
            filepath = os.path.join(directory, filename)
            with open(filepath, "r", encoding='utf-8') as f:
                content = f.read()

            #normalize name
            reg_name = filename.replace(".txt","").replace("-"," ").upper()

            #check then insert (idempotency plus data integrity)
            existing = session.query(Regulation).filter_by(name=reg_name).first()

            if not existing:
                new_reg = Regulation(
                    name = reg_name, 
                    section= DEFAULT_REGULATION_SECTION,
                    text_content= content
                )
                session.add(new_reg)
                logger.info(f"Staged regulation: {reg_name}")
                files_processed +=1
            else:
                logger.info(f'{reg_name} already exits, skipping...')
        
        except Exception as e:
            logger.error(f'failed to process file : {e}')
            raise

    return files_processed

def ingest_policy(session: Session, directory):

    if not os.path.exists(directory):
        logger.warning(f'directory not found: {directory}')
        return 0
    
    files_processed = 0

    files = sorted(f for f in os.listdir(directory) if f.endswith('.txt'))

    for filename in files:
        try:
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            pol_name = filename.replace(".txt", "").replace("-"," ").upper()

            existing = session.query(InternalPolicy).filter_by(name= pol_name).first()

            if not existing:
                new_pol = InternalPolicy(
                    name = pol_name,
                    version = DEFAULT_POLICY_VERSION,
                    text_content = content

                )
                session.add(new_pol)
                logger.info(f'Staged policy: {pol_name}')
                files_processed +=1

            else:
                logger.info(f'{pol_name} already exists, skipping..')
            
        except Exception as e:
            logger.error(f'failed to process file: {e}')
            raise
    
    return files_processed

def main():
    try:
       init_db_connection()
    except Exception as e:
        logger.critical(f'failed to connect to db: {e}')
        sys.exit(1)
    
    session = SessionLocal()

    try:
        logger.info("Starting Data Ingestion..")



        logger.info("---Phase 1: Regulation")
        reg_count = ingest_regulations(session, DATA_DIR_REGULATIONS)

        logger.info("---Phase 2: Policy")
        pol_count = ingest_policy(session, DATA_DIR_POLICIES)

        #we commit only at the very end, to ensure full atomicity, no case of regulation with missing policy

        total_changes = reg_count+pol_count

        if total_changes > 0:
            session.commit()
            logger.info(f'Commit Success: Written {reg_count} Regs & {pol_count} Policies to DB.')

        else: 
            logger.info("No new data found, DB is upto date.")
        
    except IntegrityError as ie:
        session.rollback()
        logger.critical(f'Data integrity error - constraint violation: {ie}')
        sys.exit(1)

    except Exception as e:
        session.rollback()
        logger.critical(f'Pipeline Failure: {e}')
        sys.exit(1)

    finally:
        session.close()

if __name__ == "__main__":
    main()











