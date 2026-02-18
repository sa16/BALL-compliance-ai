import logging
from sqlalchemy.orm import Session
from app.db.models import Regulation, InternalPolicy, DocumentChunk
from app.db.session import init_db_connection, SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")

logger = logging.getLogger(__name__)

def  split_text_by_paragraph(text: str)->list:

    """
    to divide parts of the text as paragraphs, split by (\n\n)
    Filter out empty strings.

    """
    chunks = text.split("\n\n")
    cleaned_chunks = [c.strip() for c in chunks if c.strip()] #empty if chunks is empty

    return cleaned_chunks

def process_regulations(session: Session)->int:
    """
    determines if text is from regulation or policy, then splits by paragraph & adds to DocumentChunk table
    """
    regs = session.query(Regulation).all()

    logger.info(f'processing {len(regs)} regulations')

    count =0

    #idempotency check: skip if regulation already exists
    for reg in regs:
        existing_chunks = session.query(DocumentChunk).filter_by(source_id=reg.id, source_type='regulation').first()
    
        if existing_chunks:
            logger.info(f'{reg.name} already exists as chunk, skipping...')
            continue

        text_chunks = split_text_by_paragraph(reg.text_content)

        for index, chunk_text in enumerate(text_chunks):
            doc_chunk = DocumentChunk(
                source_id = reg.id,
                source_type = 'regulation',
                chunk_index = index,
                text_content = chunk_text, 
                chunk_metadata ={'section': reg.section}
            )
            session.add(doc_chunk)
            count +=1

        logger.info(f'{reg.name}: {len(text_chunks)} chunks created.')

    return count

def process_policies(session: Session)->int:

    pols = session.query(InternalPolicy).all()

    logger.info(f'processing {len(pols)} policies.')

    count=0

    for pol in pols:
        existing_chunks = session.query(DocumentChunk).filter_by(source_id = pol.id, source_type = 'policy').first()

        if existing_chunks:
            logger.info(f'{pol.name} already exists as chunk, skipping...')
            continue

        text_chunks = split_text_by_paragraph(pol.text_content)

        for index, chunk_text in enumerate(text_chunks):
            doc_chunk = DocumentChunk(
                source_id= pol.id,
                source_type = 'policy',
                chunk_index = index, 
                text_content = chunk_text,
                chunk_metadata = {'version':pol.version}

            )
            session.add(doc_chunk)
            count +=1

        logger.info(f'{pol.name}: {len(text_chunks)} chunks created.')   

    return count

def main():
    try:
        init_db_connection()    
    except Exception as e:
        logger.critical(f'Failed to connect to DB {e}')     
        return
    
    session = SessionLocal()

    try:
        logger.info("Staring semantic chunking:....")

        reg_chunks = process_regulations(session)
        pol_chunks = process_policies(session)

        total = reg_chunks + pol_chunks

        if total>0:
            session.commit()
            logger.info(f'commit success: {total} chunks added to db.')
        else:
            logger.info('No new chunks created.')
    
    except Exception as e:
        session.rollback()
        logger.error(f'failed to create chunks: {e}')
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()

        


       

    

    
    




