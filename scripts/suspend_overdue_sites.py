# Automated billing suspension script
# Run with: python scripts/suspend_overdue_sites.py
from models.site import Site
from models.billing import Billing
from database import db
from datetime import datetime

def suspend_overdue_sites():
    now = datetime.utcnow()
    overdue_billings = Billing.query.filter(
        Billing.paid == False,
        Billing.due_date != None,
        Billing.due_date < now,
        Billing.status == 'active'
    ).all()
    suspended = []
    for bill in overdue_billings:
        site = Site.query.get(bill.site_id)
        if site and site.status != 'suspended':
            site.status = 'suspended'
            db.session.commit()
            suspended.append(site.id)
    print(f"Suspended sites: {suspended}")

if __name__ == "__main__":
    suspend_overdue_sites()
