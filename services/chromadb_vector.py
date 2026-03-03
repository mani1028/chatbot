# ChromaDB integration for scalable vector search
# This is a stub for integration. You must install chromadb: pip install chromadb
import os
import logging
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# Lazy-load pattern: prevent blocking download at import time
_MODEL = None
_MODEL_LOAD_ATTEMPTED = False
_EMBEDDINGS_DISABLED = os.getenv('DISABLE_EMBEDDINGS', 'false').lower() == 'true'

def _get_model():
    """Lazy-load SentenceTransformer with timeout guard."""
    global _MODEL, _MODEL_LOAD_ATTEMPTED
    
    if _EMBEDDINGS_DISABLED:
        logger.info("Embeddings disabled via DISABLE_EMBEDDINGS environment variable")
        return None
    
    if _MODEL is not None:
        return _MODEL
    
    if _MODEL_LOAD_ATTEMPTED:
        return None
    
    _MODEL_LOAD_ATTEMPTED = True
    
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("SentenceTransformer model loaded successfully")
        return _MODEL
    except Exception as e:
        logger.error(f"Failed to load SentenceTransformer model: {e}")
        return None

chroma_client = chromadb.Client(Settings(
    persist_directory="./chromadb_store"
))

def add_document(site_id, file_id, text):
    model = _get_model()
    if model is None:
        logger.warning(f"Cannot add document: embeddings unavailable")
        return
    
    collection_name = f"site_{site_id}_kb"
    collection = chroma_client.get_or_create_collection(collection_name)
    embedding = model.encode(text, convert_to_numpy=True)
    collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[{"file_id": file_id}]
    )

def query_documents(site_id, query, top_k=3):
    model = _get_model()
    if model is None:
        logger.warning(f"Cannot query documents: embeddings unavailable")
        return []
    
    collection_name = f"site_{site_id}_kb"
    collection = chroma_client.get_or_create_collection(collection_name)
    query_emb = model.encode(query, convert_to_numpy=True)
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k
    )
    return results
