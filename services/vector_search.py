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

chroma_client = chromadb.Client(Settings(
    persist_directory="./chromadb_store"
))

def load_embedding(file_id):
    """Load embedding for a file from ChromaDB metadata lookup across site collections."""
    try:
        collections = chroma_client.list_collections()
        for collection in collections:
            # Prefer site_*_kb collections used by index_site_files
            if not collection.name.endswith('_kb'):
                continue
            try:
                result = collection.get(
                    where={"file_id": file_id},
                    include=["embeddings"]
                )
                embeddings = (result or {}).get("embeddings") or []
                if embeddings:
                    return embeddings[0]
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"load_embedding failed for file_id={file_id}: {e}")
    return None

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
    """Semantic KB search via ChromaDB collection populated by index_site_files()."""
    query_emb = embed_text(query)
    if query_emb is None:
        logger.warning(f"Cannot query knowledge base for site {site_id}: embeddings unavailable")
        return []

    collection_name = f"site_{site_id}_kb"
    try:
        collection = chroma_client.get_or_create_collection(collection_name)
        emb_list = query_emb.tolist() if hasattr(query_emb, "tolist") else list(query_emb)
        raw = collection.query(
            query_embeddings=[emb_list],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        logger.warning(f"ChromaDB query failed for site {site_id}: {e}")
        return []

    results = []
    ids_meta = (raw or {}).get("metadatas") or [[]]
    distances = (raw or {}).get("distances") or [[]]
    documents = (raw or {}).get("documents") or [[]]
    if not ids_meta or not ids_meta[0]:
        return []

    for meta, distance, doc in zip(ids_meta[0], distances[0], documents[0]):
        file_id = (meta or {}).get("file_id")
        site_file = SiteFile.query.get(file_id) if file_id is not None else None
        # Chroma distances are typically L2; convert to a similarity-like score in [0,1]
        score = 1.0 / (1.0 + float(distance)) if distance is not None else 0.0
        if site_file is None:
            # Keep searchable even if SiteFile row is missing
            class _DocProxy:
                def __init__(self, filename, text):
                    self.filename = filename
                    self.text = text
            site_file = _DocProxy(filename=f"file_{file_id}", text=doc)
            site_file.id = file_id
        results.append((score, site_file))

    results.sort(reverse=True, key=lambda x: x[0])
    return results[:top_k]
