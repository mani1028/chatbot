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
    SQLALCHEMY_TRACK_MODIFICATIONS, ADMIN_USERNAME, ADMIN_PASSWORD,
    CONFIDENCE_THRESHOLD
)
from database import db, init_db
from models import Admin, FAQ, ChatLog, UnansweredQuestion
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
    
    # Add sample FAQs if database is empty
    if FAQ.query.count() == 0:
        sample_faqs = [
            FAQ(
                question="What are your business hours?",
                answer="We are open Monday to Friday, 9 AM to 6 PM. We're closed on weekends.",
                category="General"
            ),
            FAQ(
                question="How can I contact customer support?",
                answer="You can reach our support team via email at support@example.com or call 1-800-EXAMPLE.",
                category="Support"
            ),
            FAQ(
                question="What payment methods do you accept?",
                answer="We accept all major credit cards, PayPal, and bank transfers.",
                category="Billing"
            ),
            FAQ(
                question="How long does delivery take?",
                answer="Standard delivery takes 5-7 business days. Express delivery is available in 2-3 days.",
                category="Shipping"
            ),
        ]
        for faq in sample_faqs:
            db.session.add(faq)
        db.session.commit()
        print(f"Sample FAQs added to database")


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
            'is_answered': response['is_answered']
        })
    
    except Exception as e:
        print(f"Error in /api/chat: {str(e)}")
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
    Shows FAQs, chat logs, and unanswered questions
    """
    return render_template('admin_dashboard.html')


@app.route('/admin/api/faqs', methods=['GET'])
@login_required
def get_faqs():
    """
    Get all FAQs
    """
    faqs = AIService.get_all_faqs()
    return jsonify({'faqs': faqs})


@app.route('/admin/api/faq', methods=['POST'])
@login_required
def create_faq():
    """
    Create new FAQ
    """
    try:
        data = request.json
        question = data.get('question', '').strip()
        answer = data.get('answer', '').strip()
        category = data.get('category', 'General').strip()
        
        if not question or not answer:
            return jsonify({'error': 'Question and answer are required'}), 400
        
        result = AIService.add_faq(question, answer, category)
        
        if result['success']:
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/faq/<int:faq_id>', methods=['PUT'])
@login_required
def update_faq(faq_id):
    """
    Update existing FAQ
    """
    try:
        data = request.json
        question = data.get('question', '').strip() or None
        answer = data.get('answer', '').strip() or None
        category = data.get('category', '').strip() or None
        
        result = AIService.update_faq(faq_id, question, answer, category)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/api/faq/<int:faq_id>', methods=['DELETE'])
@login_required
def delete_faq(faq_id):
    """
    Delete FAQ
    """
    try:
        result = AIService.delete_faq(faq_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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


@app.route('/admin/api/stats', methods=['GET'])
@login_required
def get_stats():
    """
    Get dashboard statistics
    """
    total_chats = ChatLog.query.count()
    total_faqs = FAQ.query.count()
    answered_chats = ChatLog.query.filter(ChatLog.matched_faq_id.isnot(None)).count()
    unanswered_questions = UnansweredQuestion.query.count()
    
    # Calculate answer rate
    answer_rate = (answered_chats / total_chats * 100) if total_chats > 0 else 0
    
    return jsonify({
        'total_chats': total_chats,
        'total_faqs': total_faqs,
        'answered_chats': answered_chats,
        'answer_rate': round(answer_rate, 2),
        'unanswered_questions': unanswered_questions,
        'confidence_threshold': CONFIDENCE_THRESHOLD
    })


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
