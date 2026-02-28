from models import ClientConfig
from database import db

# Example workflow handlers. Each receives contextual parameters and returns a dict

def get_price(site_id: int, **kwargs):
    """Return pricing info from ClientConfig for a site_id."""
    try:
        # Ensure site_id is an integer
        site_id = int(site_id)
        from models import ClientConfig
        cfg = ClientConfig.query.filter_by(site_id=site_id, key='consultation_price').first()
        price = cfg.value if cfg else "Not Available"
        return {'consultation_price': price}
    except Exception as e:
        print(f"Error in get_price: {e}")
        return {'consultation_price': "Error fetching price"}

def track_order(site_id: int, order_id: str = None, **kwargs):
    """Integrate with ERP system to fetch order status."""
    # Example: Replace with real ERP endpoint and authentication
    ERP_API_URL = "https://erp.example.com/api/orders/status"
    try:
        payload = {
            "site_id": site_id,
            "order_id": order_id
        }
        # You may need to add authentication headers/tokens here
        import requests
        response = requests.post(ERP_API_URL, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                'order_id': order_id,
                'status': data.get('status', 'unknown'),
                'eta': data.get('eta', 'N/A'),
                'details': data
            }
        else:
            return {'order_id': order_id, 'status': 'error', 'eta': 'N/A', 'details': response.text}
    except Exception as e:
        print(f"ERP API error: {e}")
        return {'order_id': order_id, 'status': 'error', 'eta': 'N/A', 'details': str(e)}