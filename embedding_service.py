import logging
from openai import RateLimitError, APIConnectionError, OpenAI
import time
from dotenv import load_dotenv

load_dotenv(override=True) # ensuring it reads open api key

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"

class EmbeddingService: 

    def __init__(self):
        self.client = OpenAI()

    def get_embeddings_batch(self, text: list[str])->list[list[float]]:
        """
        creates batches of 20 text items & creates embeddings. 
        """
        clean_texts = [t.replace("\n", " ") for t in text]

        retries= 3
        delay =1

        for attempt in range(retries):
            try:
                response = self.client.embeddings.create(
                input=clean_texts,
                model=EMBEDDING_MODEL,

                )

                sorted_data = sorted(response.data, key = lambda x: x.index)

                return [item.embedding for item in sorted_data]
        
            except RateLimitError:
                logger.warning(f'Rate Limit hit, please retry in {delay}s...')
                time.sleep(delay)
                delay *=2

            except APIConnectionError:
                logger.warning(f'api connection error, please retry in {delay}s...')
                time.sleep(delay)
                delay *=2

            except Exception as e:
                logger.error(f'Batch emebedding pipeline failed: {e}')
                raise
        
        raise Exception('Embedding pipeline failed after multiple retries!')
    
embedding_service = EmbeddingService()
        



