import logging
from app.services.embedding_service import embedding_service
from qdrant_client.http import models
from sqlalchemy.orm import Session
from app.services.vector_store import init_qdrant_collection, get_qdrant_client, COLLECTION_NAME
from app.db.models import DocumentChunk
from app.db.session import init_db_connection, SessionLocal


logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 20

def process_vector_ingestion(session: Session):

    """
        -obtain unembedded chunks from postgres db 
        -create batches of 20 
        -embed batches
        -upsert batches to qdrant
        -update embedding id on postgres to match qdrant id
    """
    client = get_qdrant_client()

    chunks = session.query(DocumentChunk).filter(DocumentChunk.embedding_id.is_(None)).all()

    if not chunks:
        logger.info("No unmbedded chunks to process.")
        return
    
    logger.info(f'Found {len(chunks)} to process. Processing batch-size: {BATCH_SIZE}')
    total_success = 0

    for i in range(0, len(chunks), BATCH_SIZE):
        batch_chunks = chunks[i: i+BATCH_SIZE]

        try:
            texts = [c.text_content for c in batch_chunks]
            vectors = embedding_service.get_embeddings_batch(texts)

            points=[]

            for chunk, vector in zip(batch_chunks, vectors):
                qdrant_id = str(chunk.id)
                payload = {
                    "source_id":str(chunk.source_id),
                    "source_type":chunk.source_type,
                    "text_content":chunk.text_content,
                    "chunk_index":chunk.chunk_index,  
                }
                if chunk.chunk_metadata:
                    payload["chunk_metadata"]=chunk.chunk_metadata

                points.append(models.PointStruct(
                    id= qdrant_id,
                    vector= vector,
                    payload=payload

                ))

            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points

                )

            for chunk, point in zip(batch_chunks, points):
                chunk.embedding_id = point.id
            
            session.commit()

            total_success += len(batch_chunks)

            logger.info(f'Processed batch {i}-{i+len(batch_chunks)} ({total_success}/{len(chunks)} completed)')

        except Exception as e:
            logger.error(f'Batch failed: {e}')
            session.rollback()

            continue

    logger.info(f'Ingestion completed. Total processed: {total_success}')

def main():
    try:
        init_db_connection()
        init_qdrant_collection()
    except Exception as e:
        logger.critical(f'Failed to connect to infra: {e}')
        raise 
        return
    
    session = SessionLocal()
    try:
        process_vector_ingestion(session)

    finally:
        session.close()

if __name__=="__main__":
    main()
            