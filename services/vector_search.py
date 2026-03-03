import os
import logging
from PyPDF2 import PdfReader
from models.file_manager import SiteFile
from docx import Document
import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.config import Settings

# Lazy-load pattern: prevent blocking download at import time
_MODEL = None
_MODEL_LOAD_ATTEMPTED = False
_EMBEDDINGS_DISABLED = os.getenv('DISABLE_EMBEDDINGS', 'false').lower() == 'true'
_ST_UTIL = None

logger = logging.getLogger(__name__)

def _get_st_util():
    """Lazy-load util module from sentence-transformers (lightweight, no model load)."""
    global _ST_UTIL
    if _ST_UTIL is None:
        try:
            from sentence_transformers import util as st_util
            _ST_UTIL = st_util
        except ImportError:
            logger.warning("sentence_transformers.util not available")
            _ST_UTIL = False  # Mark as failed
    return _ST_UTIL if _ST_UTIL is not False else None

def _get_model():
    """Lazy-load SentenceTransformer with timeout guard. Returns None if disabled or failed."""
    global _MODEL, _MODEL_LOAD_ATTEMPTED
    
    if _EMBEDDINGS_DISABLED:
        logger.info("Embeddings disabled via DISABLE_EMBEDDINGS environment variable")
        return None
    
    if _MODEL is not None:
        return _MODEL
    
    if _MODEL_LOAD_ATTEMPTED:
        return None  # Already tried and failed
    
    _MODEL_LOAD_ATTEMPTED = True
    try:
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Model load exceeded 10 second timeout")
        
        # Set timeout (Windows doesn't support SIGALRM, so this is best-effort)
        old_handler = signal.signal(signal.SIGALRM, timeout_handler) if hasattr(signal, 'SIGALRM') else None
        if old_handler is not None:
            signal.alarm(10)
        
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        
        if old_handler is not None:
            signal.alarm(0)  # Cancel timeout
        
        logger.info("SentenceTransformer model loaded successfully")
        return _MODEL
    except Exception as e:
        logger.error(f"Failed to load SentenceTransformer model: {e}. Embeddings will be unavailable.")
        _MODEL_LOAD_ATTEMPTED = True
        return None

def embed_text(text):
    """Embed text using lazy-loaded MODEL. Returns None if model unavailable."""
    model = _get_model()
    if model is None:
        logger.warning(f"Model unavailable, cannot embed text: {text[:50]}")
        return None
    try:
        return model.encode(text, convert_to_numpy=True)
    except Exception as e:
        logger.error(f"Failed to embed text: {e}")
        return None

def load_embedding(file_id):
    """Load embedding for a file. Placeholder implementation."""
    # TODO: Implement actual embedding retrieval from storage
    # For now, return None
    return None

chroma_client = chromadb.Client(Settings(
    persist_directory="./chromadb_store"
))

def extract_text_from_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        text = "\n".join(page.extract_text() or '' for page in reader.pages)
        return text
    except Exception:
        return ''

def extract_text_from_txt(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        return '\n'.join([p.text for p in doc.paragraphs])
    except Exception:
        return ''

def extract_text_from_url(url):
    try:
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return soup.get_text()
    except Exception:
        return ''

def index_site_files(site_id):
    files = SiteFile.query.filter_by(site_id=site_id).all()
    collection_name = f"site_{site_id}_kb"
    collection = chroma_client.get_or_create_collection(collection_name)
    for f in files:
        abs_path = os.path.join('static', 'uploads', 'sites', str(site_id), f.filename)
        text = ''
        if f.file_type == 'pdf':
            text = extract_text_from_pdf(abs_path)
        elif f.file_type == 'txt':
            text = extract_text_from_txt(abs_path)
        elif f.file_type == 'docx':
            text = extract_text_from_docx(abs_path)
        elif f.file_type == 'url':
            text = extract_text_from_url(f.file_path)
        if text:
            embedding = embed_text(text)
            if embedding is not None:
                collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[{"file_id": f.id}]
                )

def query_knowledge_base(site_id, query, top_k=3):
    files = SiteFile.query.filter_by(site_id=site_id).all()
    query_emb = embed_text(query)
    results = []
    if query_emb is None:
        logger.warning(f"Cannot query knowledge base for site {site_id}: embeddings unavailable")
        return []
    
    st_util = _get_st_util()
    if st_util is None:
        logger.warning(f"Cannot query knowledge base for site {site_id}: st_util unavailable")
        return []
    
    for f in files:
        emb = load_embedding(f.id)
        if emb is not None:
            score = float(st_util.cos_sim(query_emb, emb))
            results.append((score, f))
    results.sort(reverse=True, key=lambda x: x[0])
    return results[:top_k]
