import logging
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
import time

# logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
# logger = logging.getLogger(__name__)

logger = logging.getLogger("json_logger")

COLLECTION_NAME = "compliance_chunks"

VECTOR_SIZE  = 1536 # this is model specific, an embedding model & dimension mismatch will cause a crash. 

DEFAULT_TIMEOUT=10.0

def get_qdrant_client():
    """ 
    obtain host & port names from env variables. 
    Returns a qrant client instance
    
    """
    #refactored to support both Local (http://localhost:6333) and Cloud (https://xyz.qdrant.tech)

    cloud_url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    try:
        if cloud_url:
            # logger.info(f"connecting to qdrant cloud: {cloud_url[:20]}...")
            logger.info({"event":"connecting_to_qdrant_Client"})
            return QdrantClient(url=cloud_url, api_key=api_key, timeout=DEFAULT_TIMEOUT)
    except Exception as e:
        logger.error({"event": "qdrant_client_init_failed", "error": str(e)})
        raise


   
    
    # host = os.getenv("QDRANT_HOST", "localhost")
    # port = int(os.getenv("QDRANT_PORT", 6333))
    # logger.info(f"connecting to qdrant local: {host}:{port}")

    # return QdrantClient(host=host, port=port)

#setting up the vector collection in qdrant

def init_qdrant_collection():
    """
    idempotent initialization of the vector collection (skips if already exists)

    """
    for attempt in range(5):
        try:
            client = get_qdrant_client()
            break
        except Exception:
            time.sleep(2**attempt)

    try: 
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)

        if not exists:
            # logger.info(f'Creating Qdrant Collection: {COLLECTION_NAME}')
            logger.info({"event": "creating_qdrant_collection", "collection": COLLECTION_NAME})
            client.create_collection(COLLECTION_NAME, 
            vectors_config = models.VectorParams(
                size= VECTOR_SIZE,
                distance= models.Distance.COSINE
                )
            )
            # logger.info(f"{COLLECTION_NAME} collection created succesfully!")
            logger.info({"event": "qdrant_collection_created", "collection": COLLECTION_NAME})

        else: 
            # logger.info(f'{COLLECTION_NAME} already exists. Waiting for data load.')
            logger.info({"event": "qdrant_collection_exists", "collection": COLLECTION_NAME})

        logger.info({"event":"Verifying_qdrant_indexes"})

        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="source_type",
            field_schema=models.PayloadSchemaType.KEYWORD
        )

        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="source_id",
            field_schema=models.PayloadSchemaType.KEYWORD
        )

        # logger.info("indexes set.")
        logger.info({"event": "qdrant_indexes_set"})

    except Exception as e:
        # logger.error(f'Failed to initialize Qdrant: {e}')
        logger.error({"event": "qdrant_init_failed", "error": str(e)})
        raise

if __name__ == "__main__":
    init_qdrant_collection()





        


