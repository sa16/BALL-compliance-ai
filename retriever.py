import logging
from sqlalchemy.orm import Session
from embedding_service import embedding_service
from qdrant_client.http import models
from database import init_db_connection, SessionLocal
from vector_store import COLLECTION_NAME, get_qdrant_client
from models import DocumentChunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.3
# higher thresholds might seem safer to have, however, a lower threshold improves recall volume. Then filter out results,
# this way subtle regulations are harder to miss
# high threshold recall results might be misleading.....for instance, if nothing is recalled, this might be interpreted as no matching
#regulations

TOP_K = 5

def retrieve_relevant_chunks(query: str, session: Session,limit: int = TOP_K)-> list[tuple[DocumentChunk, float]]:
    """
    **Semantic Search Layer**

    -Embed the <query>
    -Search qdrant from similar vectors
    -apply similarity threshold to filter & return top_k
    -join with postgres to capture full relevant text
    
    return: list of tuples
    """

    client = get_qdrant_client()

    try:
        query_vector = embedding_service.get_embedding(query)
    except Exception as e:
        logger.error(f'failed to embedd query: {e}')
        return []
    
    try:
        search_result = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            with_payload=True,
            score_threshold=SIMILARITY_THRESHOLD
        ).points

    except Exception as e:
        logger.error(f'Qdrant search failed: {e}')
        return []

    if not search_result:
        logger.info("No relevant results found.")
        return []
    
    

    # for point in search_result:
    #     chunk_id = point.id # primary id on postgres db to join on
    #     score  = point.score
    
    #     #inner join (qdrant & postgres)
    #     doc_chunk = session.query(DocumentChunk).filter_by(id=chunk_id).first()

    #initial approach is not optimal at scale (O(N+1)) below batching approach runs in constant time.

    #batching qdrant results:
    score_map = {points.id:points.score for points in search_result}
    target_ids = list(score_map.keys())

    relevant_chunks=[]

    try:
        chunks = session.query(DocumentChunk).filter(DocumentChunk.id.in_(target_ids)).all()
    except Exception as e:
        logger.error(f'failed to fetch from postgres db: {e}')
        return []

    chunk_map = {str(c.id):c for c in chunks}

    for points in search_result:
        chunk_id = points.id
        if chunk_id in chunk_map:
            doc_chunk = chunk_map[chunk_id]
            score= points.score
            relevant_chunks.append((doc_chunk, score))
            logger.info(f'Found: [{score:.2f}] {doc_chunk.source_type.upper()}: {doc_chunk.text_content[:50]}')
        else:
            logger.error("data drift detected: did not find corresponding id in postgres")

    return relevant_chunks


if __name__ == "__main__":
    try:
        init_db_connection()
        session = SessionLocal()

        test_query = "What are the requirements for exit strategies?"
        logger.info(f'testing retreival for test query: {test_query}')
        results = retrieve_relevant_chunks(test_query, session, limit=TOP_K)

        logger.info(f'returned {len(results)} chunks.')

        for chunk, score in results:
            logger.info(f'[{score:.2f}] {chunk.source_type.upper()} - {chunk.text_content[:100]}')

    except Exception as e:
        logger.error(f'Smoke test failed: {e}')
    finally:
        session.close()
        






    
