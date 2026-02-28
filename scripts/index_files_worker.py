# Background worker for file indexing
# Run with: python scripts/index_files_worker.py
from services.vector_search import index_site_files
from models.site import Site
from database import db
import time

INTERVAL = 60  # seconds between checks

def run_worker():
    while True:
        sites = Site.query.all()
        for site in sites:
            try:
                print(f"Indexing files for site {site.id}...")
                index_site_files(site.id)
            except Exception as e:
                print(f"Error indexing site {site.id}: {e}")
        db.session.remove()
        time.sleep(INTERVAL)

if __name__ == "__main__":
    run_worker()
