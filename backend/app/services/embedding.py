import numpy as np
from sentence_transformers import SentenceTransformer
from app.config import settings
from app.utils.helpers import logger

class EmbeddingService:
    def __init__(self):
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL_NAME}...")
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        # Store embedding dimension (for all-MiniLM-L6-v2, this is 384)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding model loaded. Dimension size: {self.dimension}")
    
    def embed_texts(self, texts: list) -> np.ndarray:
        """Generate embeddings for a list of texts
        Returns: numpy array of embeddings (float32)
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts)
        return np.array(embeddings).astype(np.float32)
    
    def embed_query(self, query: str) -> np.ndarray:
        """Generate embedding for a single query string
        Returns: numpy array of the query embedding (float32)
        """
        logger.info(f"Generating embedding for query: '{query[:50]}...'")
        embedding = self.model.encode([query])
        return np.array(embedding).astype(np.float32)

embedding_service = EmbeddingService()
