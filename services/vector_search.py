def embed_text(text):
    """Embed text using the global MODEL."""
    return MODEL.encode(text, convert_to_numpy=True)

def load_embedding(file_id):
    """Load embedding for a file. Placeholder implementation."""
    # TODO: Implement actual embedding retrieval from storage
    # For now, return None
    return None

import os
from sentence_transformers import SentenceTransformer, util as st_util
from PyPDF2 import PdfReader
from models.file_manager import SiteFile
from docx import Document
import requests
from bs4 import BeautifulSoup
import chromadb
from chromadb.config import Settings

MODEL = SentenceTransformer('all-MiniLM-L6-v2')

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
            embedding = MODEL.encode(text, convert_to_numpy=True)
            collection.add(
                documents=[text],
                embeddings=[embedding],
                metadatas=[{"file_id": f.id}]
            )

def query_knowledge_base(site_id, query, top_k=3):
    files = SiteFile.query.filter_by(site_id=site_id).all()
    query_emb = embed_text(query)
    results = []
    for f in files:
        emb = load_embedding(f.id)
        if emb is not None:
            score = float(st_util.cos_sim(query_emb, emb))
            results.append((score, f))
    results.sort(reverse=True, key=lambda x: x[0])
    return results[:top_k]
