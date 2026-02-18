import logging
import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

COLLECTION_NAME = "compliance_chunks"

VECTOR_SIZE  = 1536 # this is model specific, an embedding model & dimension mismatch will cause a crash. 

def get_qdrant_client():
    """ 
    obtain host & port names from env variables. 
    Returns a qrant client instance
    
    """
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", 6333))

    return QdrantClient(host=host, port=port)

#setting up the vector collection in qdrant

def init_qdrant_collection():
    """
    idempotent initialization of the vector collection (skips if already exists)

    """
    client = get_qdrant_client()

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





        


