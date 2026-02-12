# Create this as 'init_site.py' and run it: python init_site.py
from app import app
from database import db
from models.site import Site

with app.app_context():
    if not Site.query.get(1):
        test_site = Site(
            id=1,
            name='Test Site',
            domain='localhost',
            domain_whitelist='localhost',
            bot_name='HelperBot'
        )
        db.session.add(test_site)
        db.session.commit()
        print("Successfully created Site ID 1")