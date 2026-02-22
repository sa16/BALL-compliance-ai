import logging
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

COLLECTION_NAME = "compliance_chunks"

VECTOR_SIZE  = 1536 # this is model specific, an embedding model & dimension mismatch will cause a crash. 

def get_qdrant_client():
    """ 
    obtain host & port names from env variables. 
    Returns a qrant client instance
    
    """
    #refactored to support both Local (http://localhost:6333) and Cloud (https://xyz.qdrant.tech)
    url = os.getenv("QDRANT_URL", "https://localhost")
   # port = int(os.getenv("QDRANT_PORT", 6333))
    api_key= os.getenv("QDRANT_API_KEY")

    return QdrantClient(url=url, api_key=api_key)

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
            logger.info(f'Creating Qdrant Collection: {COLLECTION_NAME}')
            client.create_collection(COLLECTION_NAME, 
            vectors_config = models.VectorParams(
                size= VECTOR_SIZE,
                distance= models.Distance.COSINE
                )
            )
            logger.info(f"{COLLECTION_NAME} collection created succesfully!")

        else: 
            logger.info(f'{COLLECTION_NAME} already exists. Waiting for data load.')

    except Exception as e:
        logger.error(f'Failed to initialize Qdrant: {e}')
        raise

if __name__ == "__main__":
    init_qdrant_collection()





        


