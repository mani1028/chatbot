from app import app
from models import Site
with app.app_context():
    print([(s.name, s.status) for s in Site.query.all()])