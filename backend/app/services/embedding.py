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
        """Generate L2-normalized embeddings for a list of texts.
        
        Using normalize_embeddings=True ensures all output vectors have unit norm (||v|| = 1.0).
        This allows FAISS IndexFlatL2 squared distances (D = ||u - v||^2) to have a 1-to-1
        equivalence with Cosine Similarity via: Cosine_Similarity = 1 - (D / 2.0).
        
        Returns: numpy array of embeddings (float32) of shape (len(texts), dimension)
        """
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        
        logger.info(f"Generating normalized embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return np.array(embeddings).astype(np.float32)
    
    def embed_query(self, query: str) -> np.ndarray:
        """Generate L2-normalized embedding for a single query string.
        
        Returns: numpy array of the query embedding (float32) of shape (1, dimension)
        """
        if not query or not query.strip():
            logger.warning("Empty or whitespace query provided. Returning zero embedding.")
            return np.zeros((1, self.dimension), dtype=np.float32)
            
        logger.info(f"Generating normalized embedding for query: '{query[:50]}...'")
        embedding = self.model.encode([query], normalize_embeddings=True)
        return np.array(embedding).astype(np.float32)

embedding_service = EmbeddingService()
