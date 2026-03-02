# ChromaDB integration for scalable vector search
# This is a stub for integration. You must install chromadb: pip install chromadb
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

MODEL = SentenceTransformer('all-MiniLM-L6-v2')

chroma_client = chromadb.Client(Settings(
    persist_directory="./chromadb_store"
))

def add_document(site_id, file_id, text):
    collection_name = f"site_{site_id}_kb"
    collection = chroma_client.get_or_create_collection(collection_name)
    embedding = MODEL.encode(text, convert_to_numpy=True)
    collection.add(
        documents=[text],
        embeddings=[embedding],
        metadatas=[{"file_id": file_id}]
    )

def query_documents(site_id, query, top_k=3):
    collection_name = f"site_{site_id}_kb"
    collection = chroma_client.get_or_create_collection(collection_name)
    query_emb = MODEL.encode(query, convert_to_numpy=True)
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k
    )
    return results
