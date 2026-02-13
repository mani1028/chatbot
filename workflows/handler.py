from models import ClientConfig
from database import db

# Example workflow handlers. Each receives contextual parameters and returns a dict

def get_price(client_id: int, **kwargs):
    """Return pricing info from ClientConfig for a client_id."""
    try:
        # Ensure client_id is an integer
        client_id = int(client_id)
        
        cfg = ClientConfig.query.filter_by(client_id=client_id, key='consultation_price').first()
        
        price = cfg.value if cfg else "Not Available"
        return {'consultation_price': price}
    except Exception as e:
        print(f"Error in get_price: {e}")
        return {'consultation_price': "Error fetching price"}

def track_order(client_id: int, order_id: str = None, **kwargs):
    """Placeholder: in a real system this would call an external API to fetch order status."""
    return {'order_id': order_id, 'status': 'processing', 'eta': '2 days'}