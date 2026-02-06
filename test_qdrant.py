import logging
import uuid
import random
from qdrant_client.http import models
from vector_store import get_qdrant_client, init_qdrant_collection, COLLECTION_NAME, VECTOR_SIZE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

def run_dry_test():
    """
    openai tokens cost money. Will use this dry run to test Qdrant, using fake vectors 
    """

    client=get_qdrant_client() #qdrant instance

    init_qdrant_collection() #ensure connectioning to qdrant

    fake_vector = [random.random() for _ in range(VECTOR_SIZE)] #these look like vectors openai would generate, but are dummy vectors
    fake_id = str(uuid.uuid4())

    fake_payload = {
        "source_type": "dry_test_run",
        "text_content": "This is a test chunk to verify Qdrant infra."
    }

    try: 
        logger.info("Uploading dummy vectors to Qdrant...")

        #upsert
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id = fake_id,
                    vector= fake_vector,
                    payload=fake_payload
                )
            ]

        )
        logger.info(f'upload succesfull. ID: {fake_id}')

        #test similiarity search
        logger.info("Testing basic retreival & similarity noise....")

        search_result= client.query_points(
            collection_name = COLLECTION_NAME,
            query = fake_vector,
            limit=1
        ).points

        if search_result:
            found_payload = search_result[0].payload
            logger.info(f"Basic search sucessful, found: {found_payload['text_content']}")
        else:
            logger.error("basic search failed. Vector not found.")
            return
        

        logger.info("Testing metadata filtering: (filtering by source-type)")
        filter_results= client.query_points(
            collection_name = COLLECTION_NAME,
            query = fake_vector,
            limit =1,
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(key = "source_type", match=models.MatchValue(value="dry_test_run"))
                ]
            )
        ).points

        if filter_results:
            logger.info('Metadata filter successful! Qdrant is respecting the where clause.')
        else:
            logger.error('Metadata filer failed. Critical!')

    except Exception as e:
        logger.error(f'dry test run failed: {e}')
        raise

if __name__ == "__main__":
    run_dry_test()
        





