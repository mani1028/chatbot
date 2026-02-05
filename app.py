"""
Main Flask application for AI Chatbot
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
import uuid
import os

# Import config and database
from config import (
    SECRET_KEY, DEBUG, SQLALCHEMY_DATABASE_URI, 
    SQLALCHEMY_TRACK_MODIFICATIONS, ADMIN_USERNAME, ADMIN_PASSWORD
)
from database import db, init_db
from models import Admin, Intent, FAQ, ChatLog, UnansweredQuestion, Lead
from ai_service import AIService

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['DEBUG'] = DEBUG
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

# Initialize database
db.init_app(app)

# Initialize database on app creation
with app.app_context():
    init_db(app)
    # Create default admin if doesn't exist
    if Admin.query.filter_by(username=ADMIN_USERNAME).first() is None:
        admin = Admin(username=ADMIN_USERNAME)
        admin.set_password(ADMIN_PASSWORD)
        db.session.add(admin)
        db.session.commit()
        print(f"Default admin created: username={ADMIN_USERNAME}")
    
    # Add sample intents if database is empty
    if Intent.query.count() == 0:
        sample_intents = [
            Intent(
                intent_name="Business Hours",
                category="General",
                short_response="We're open Monday-Friday, 9 AM to 6 PM.",
                detailed_response="Our business hours are:\n- Monday to Friday: 9:00 AM - 6:00 PM\n- Saturday & Sunday: Closed\n- Holidays: Closed",
                requires_handoff=False
            ),
            Intent(
                intent_name="Contact Support",
                category="Support",
                short_response="You can reach us via email at support@example.com or call 1-800-EXAMPLE.",
                detailed_response="Contact Support:\n- Email: support@example.com\n- Phone: 1-800-EXAMPLE\n- Hours: Monday-Friday, 9 AM-6 PM\n- Response time: Usually within 24 hours",
                requires_handoff=True
            ),
            Intent(
                intent_name="Payment Methods",
                category="Pricing",
                short_response="We accept all major credit cards, PayPal, and bank transfers.",
                detailed_response="Accepted Payment Methods:\n- Visa, Mastercard, American Express\n- PayPal\n- Bank transfers (ACH)\n- Apple Pay & Google Pay\nAll payments are processed securely with SSL encryption.",
                requires_handoff=False
            ),
            Intent(
                intent_name="Shipping & Delivery",
                category="Support",
                short_response="Standard delivery takes 5-7 business days. Express delivery available in 2-3 days.",
                detailed_response="Shipping Options:\n- Standard: 5-7 business days\n- Express: 2-3 business days\n- Overnight: 1 business day\nFree shipping on orders over $50.",
                requires_handoff=False
            ),
        ]
        for intent in sample_intents:
            intent.set_training_phrases([intent.intent_name.lower()])
            db.session.add(intent)
        db.session.commit()
        print(f"Sample intents added to database")


def login_required(f):
    """
    Decorator to require admin login for routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """
    Main chat page - served to users
    """
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    API endpoint for chat messages
    Receives user message and returns bot response
    """
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        
        # Get or create session ID for user
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Get bot response
        response = AIService.get_bot_response(user_message, session['session_id'])
        
        return jsonify({
            'success': True,
            'message': response['response'],
            'confidence': response['confidence'],
            'message_type': response['message_type'],
            'requires_handoff': response['requires_handoff']
        })
    
    except Exception as e:
        print(f"Error in /api/chat: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/lead', methods=['POST'])
def save_lead():
    """
    API endpoint to save lead information from handoff form
    """
    try:
        data = request.json
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        message = data.get('message', '').strip()
        intent_id = data.get('intent_id')
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        result = AIService.save_lead(name, email, phone, message, intent_id, session['session_id'])
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    
    except Exception as e:
        print(f"Error in /api/lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Admin login page
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Find admin user
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """
    Admin logout
    """
    session.pop('admin_id', None)
    return redirect(url_for('index'))


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """
    Admin dashboard page
    Shows intents, chat logs, and leads
    """
    return render_template('admin_dashboard.html')


# ============ INTENT MANAGEMENT ENDPOINTS ============

@app.route('/admin/api/intents', methods=['GET'])
@login_required
def get_intents():
    """
    Get all intents
    """
    intents = AIService.get_all_intents()
    return jsonify({'intents': intents})


@app.route('/admin/api/intent', methods=['POST'])
@login_required
def create_intent():
    """
    Create new intent
    """
    try:
        data = request.json
        intent_name = data.get('intent_name', '').strip()
        training_phrases = data.get('training_phrases', [])
        short_response = data.get('short_response', '').strip()
        detailed_response = data.get('detailed_response', '').strip()
        category = data.get('category', 'General').strip()
        requires_handoff = data.get('requires_handoff', False)
        
        if not intent_name or not short_response or not detailed_response:
            return jsonify({'error': 'Intent name, short response, and detailed response are required'}), 400
        
        result = AIService.add_intent(
            intent_name, training_phrases, short_response, detailed_response,
            category, requires_handoff
        )
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/intent/<int:intent_id>', methods=['PUT'])
@login_required
def update_intent(intent_id):
    """
    Update existing intent
    """
    try:
        data = request.json
        intent_name = data.get('intent_name', '').strip() or None
        training_phrases = data.get('training_phrases')
        short_response = data.get('short_response', '').strip() or None
        detailed_response = data.get('detailed_response', '').strip() or None
        category = data.get('category', '').strip() or None
        requires_handoff = data.get('requires_handoff')
        
        result = AIService.update_intent(
            intent_id, intent_name, training_phrases, short_response,
            detailed_response, category, requires_handoff
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/intent/<int:intent_id>', methods=['DELETE'])
@login_required
def delete_intent(intent_id):
    """
    Delete intent
    """
    try:
        result = AIService.delete_intent(intent_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ LEGACY FAQ ENDPOINTS (Backward Compatibility) ============

@app.route('/admin/api/faqs', methods=['GET'])
@login_required
def get_faqs():
    """
    Get all FAQs (legacy)
    """
    faqs = AIService.get_all_faqs()
    return jsonify({'faqs': faqs})


# ============ CHAT LOG & ANALYTICS ENDPOINTS ============

@app.route('/admin/api/chat-logs', methods=['GET'])
@login_required
def get_chat_logs():
    """
    Get recent chat logs
    """
    limit = request.args.get('limit', 50, type=int)
    logs = AIService.get_chat_logs(limit)
    return jsonify({'logs': logs})


@app.route('/admin/api/unanswered-questions', methods=['GET'])
@login_required
def get_unanswered_questions():
    """
    Get frequently unanswered questions
    """
    limit = request.args.get('limit', 50, type=int)
    questions = AIService.get_unanswered_questions(limit)
    return jsonify({'questions': questions})


# ============ LEAD MANAGEMENT ENDPOINTS ============

@app.route('/admin/api/leads', methods=['GET'])
@login_required
def get_leads():
    """
    Get all leads
    """
    limit = request.args.get('limit', 100, type=int)
    leads = AIService.get_all_leads(limit)
    return jsonify({'leads': leads})


@app.route('/admin/api/lead/<int:lead_id>', methods=['PUT'])
@login_required
def update_lead(lead_id):
    """
    Update lead status and notes
    """
    try:
        data = request.json
        status = data.get('status')
        assigned_to = data.get('assigned_to')
        notes = data.get('notes')
        
        result = AIService.update_lead(lead_id, status, assigned_to, notes)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ DASHBOARD STATS ENDPOINT ============

@app.route('/admin/api/stats', methods=['GET'])
@login_required
def get_stats():
    """
    Get dashboard statistics
    """
    total_chats = ChatLog.query.count()
    total_intents = Intent.query.count()
    answered_chats = ChatLog.query.filter(ChatLog.matched_intent_id.isnot(None)).count()
    unanswered_questions = UnansweredQuestion.query.count()
    new_leads = Lead.query.filter_by(status='new').count()
    
    # Calculate answer rate
    answer_rate = (answered_chats / total_chats * 100) if total_chats > 0 else 0
    
    return jsonify({
        'total_chats': total_chats,
        'total_intents': total_intents,
        'answered_chats': answered_chats,
        'answer_rate': round(answer_rate, 2),
        'unanswered_questions': unanswered_questions,
        'new_leads': new_leads
    })


# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    """
    Handle 404 errors
    """
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """
    Handle 500 errors
    """
    print(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Run Flask app
    print("=" * 50)
    print("AI Chatbot Server Starting...")
    print("=" * 50)
    print(f"Admin Login: http://localhost:5000/admin/login")
    print(f"Username: {ADMIN_USERNAME}")
    print(f"Password: {ADMIN_PASSWORD}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=DEBUG)


def login_required(f):
    """
    Decorator to require admin login for routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """
    Main chat page - served to users
    """
    return render_template('chat.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """
    API endpoint for chat messages
    Receives user message and returns bot response
    """
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        
        # Get or create session ID for user
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        # Get bot response
        response = AIService.get_bot_response(user_message, session['session_id'])
        
        return jsonify({
            'success': True,
            'message': response['response'],
            'confidence': response['confidence'],
            'message_type': response['message_type'],
            'requires_handoff': response['requires_handoff']
        })
    
    except Exception as e:
        print(f"Error in /api/chat: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/lead', methods=['POST'])
def save_lead():
    """
    API endpoint to save lead information from handoff form
    """
    try:
        data = request.json
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        message = data.get('message', '').strip()
        intent_id = data.get('intent_id')
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        result = AIService.save_lead(name, email, phone, message, intent_id, session['session_id'])
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    
    except Exception as e:
        print(f"Error in /api/lead: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Admin login page
    """
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Find admin user
        admin = Admin.query.filter_by(username=username).first()
        
        if admin and admin.check_password(password):
            session['admin_id'] = admin.id
            session.permanent = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """
    Admin logout
    """
    session.pop('admin_id', None)
    return redirect(url_for('index'))


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """
    Admin dashboard page
    Shows intents, chat logs, and leads
    """
    return render_template('admin_dashboard.html')


# ============ INTENT MANAGEMENT ENDPOINTS ============

@app.route('/admin/api/intents', methods=['GET'])
@login_required
def get_intents():
    """
    Get all intents
    """
    intents = AIService.get_all_intents()
    return jsonify({'intents': intents})


@app.route('/admin/api/intent', methods=['POST'])
@login_required
def create_intent():
    """
    Create new intent
    """
    try:
        data = request.json
        intent_name = data.get('intent_name', '').strip()
        training_phrases = data.get('training_phrases', [])
        short_response = data.get('short_response', '').strip()
        detailed_response = data.get('detailed_response', '').strip()
        category = data.get('category', 'General').strip()
        requires_handoff = data.get('requires_handoff', False)
        
        if not intent_name or not short_response or not detailed_response:
            return jsonify({'error': 'Intent name, short response, and detailed response are required'}), 400
        
        result = AIService.add_intent(
            intent_name, training_phrases, short_response, detailed_response,
            category, requires_handoff
        )
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/intent/<int:intent_id>', methods=['PUT'])
@login_required
def update_intent(intent_id):
    """
    Update existing intent
    """
    try:
        data = request.json
        intent_name = data.get('intent_name', '').strip() or None
        training_phrases = data.get('training_phrases')
        short_response = data.get('short_response', '').strip() or None
        detailed_response = data.get('detailed_response', '').strip() or None
        category = data.get('category', '').strip() or None
        requires_handoff = data.get('requires_handoff')
        
        result = AIService.update_intent(
            intent_id, intent_name, training_phrases, short_response,
            detailed_response, category, requires_handoff
        )
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/intent/<int:intent_id>', methods=['DELETE'])
@login_required
def delete_intent(intent_id):
    """
    Delete intent
    """
    try:
        result = AIService.delete_intent(intent_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ LEGACY FAQ ENDPOINTS (Backward Compatibility) ============

@app.route('/admin/api/faqs', methods=['GET'])
@login_required
def get_faqs():
    """
    Get all FAQs (legacy)
    """
    faqs = AIService.get_all_faqs()
    return jsonify({'faqs': faqs})


# ============ CHAT LOG & ANALYTICS ENDPOINTS ============

@app.route('/admin/api/chat-logs', methods=['GET'])
@login_required
def get_chat_logs():
    """
    Get recent chat logs
    """
    limit = request.args.get('limit', 50, type=int)
    logs = AIService.get_chat_logs(limit)
    return jsonify({'logs': logs})


@app.route('/admin/api/unanswered-questions', methods=['GET'])
@login_required
def get_unanswered_questions():
    """
    Get frequently unanswered questions
    """
    limit = request.args.get('limit', 50, type=int)
    questions = AIService.get_unanswered_questions(limit)
    return jsonify({'questions': questions})


# ============ LEAD MANAGEMENT ENDPOINTS ============

@app.route('/admin/api/leads', methods=['GET'])
@login_required
def get_leads():
    """
    Get all leads
    """
    limit = request.args.get('limit', 100, type=int)
    leads = AIService.get_all_leads(limit)
    return jsonify({'leads': leads})


@app.route('/admin/api/lead/<int:lead_id>', methods=['PUT'])
@login_required
def update_lead(lead_id):
    """
    Update lead status and notes
    """
    try:
        data = request.json
        status = data.get('status')
        assigned_to = data.get('assigned_to')
        notes = data.get('notes')
        
        result = AIService.update_lead(lead_id, status, assigned_to, notes)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ DASHBOARD STATS ENDPOINT ============

@app.route('/admin/api/stats', methods=['GET'])
@login_required
def get_stats():
    """
    Get dashboard statistics
    """
    total_chats = ChatLog.query.count()
    total_intents = Intent.query.count()
    answered_chats = ChatLog.query.filter(ChatLog.matched_intent_id.isnot(None)).count()
    unanswered_questions = UnansweredQuestion.query.count()
    new_leads = Lead.query.filter_by(status='new').count()
    
    # Calculate answer rate
    answer_rate = (answered_chats / total_chats * 100) if total_chats > 0 else 0
    
    return jsonify({
        'total_chats': total_chats,
        'total_intents': total_intents,
        'answered_chats': answered_chats,
        'answer_rate': round(answer_rate, 2),
        'unanswered_questions': unanswered_questions,
        'new_leads': new_leads
    })


# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    """
    Handle 404 errors
    """
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """
    Handle 500 errors
    """
    print(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Run Flask app
    print("=" * 50)
    print("AI Chatbot Server Starting...")
    print("=" * 50)
    print(f"Admin Login: http://localhost:5000/admin/login")
    print(f"Username: {ADMIN_USERNAME}")
    print(f"Password: {ADMIN_PASSWORD}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=DEBUG)




@app.route('/admin/api/faqs', methods=['GET'])
@login_required
def get_faqs():
    """
    Get all FAQs (legacy)
    """
    faqs = AIService.get_all_faqs()
    return jsonify({'faqs': faqs})
