# Deployment Status & Guide

**Last Updated**: March 1, 2026  
**Current Status**: ✅ Development Ready | ⚠️ Production Needs Configuration

---

## System Status

### ✅ Core Components Ready
- Flask application framework
- SQLite database with ORM models
- Multi-tenant architecture with site isolation
- Admin and super admin dashboards
- intent detection engine with fuzzy matching
- LLM integration (OpenAI, with free alternatives available)
- Vector search/semantic search via ChromaDB
- File upload/management system
- Chat widget and embed functionality

### ⚠️ Requires Configuration for Production
- Database (recommend PostgreSQL instead of SQLite)
- Web server (recommend Gunicorn + Nginx reverse proxy)
- SSL/TLS certificates for HTTPS
- Email service configuration
- Backup strategy
- Monitoring and logging setup
- Rate limiting and DDoS protection

---

## Development Environment

### Running Locally
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create .env file
cp .env.example .env
# Edit .env and add OPENAI_API_KEY

# 3. Start Flask server
python app.py

# 4. Access at http://localhost:5000
```

### Default Credentials
- Admin login: `admin` / `admin123`
- Super admin: Created via database

---

## Production Deployment Checklist

### Before Launch
- [ ] Change SECRET_KEY in config.py
- [ ] Use strong admin passwords
- [ ] Set up PostgreSQL database
- [ ] Configure backup strategy
- [ ] Set up monitoring (Sentry, DataDog, etc.)
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Configure rate limiting
- [ ] Set up email service
- [ ] Test all admin functions
- [ ] Load test the system

### Recommended Stack
```
┌─────────────────────────────────────────┐
│ Nginx (Reverse Proxy, SSL)              │
├─────────────────────────────────────────┤
│ Gunicorn (WSGI App Server - 4+ workers) │
├─────────────────────────────────────────┤
│ Flask Application                       │
├─────────────────────────────────────────┤
│ PostgreSQL (Database)                   │
├─────────────────────────────────────────┤
│ Redis (Caching, Session Store)          │
├─────────────────────────────────────────┤
│ ChromaDB (Vector Store)                 │
└─────────────────────────────────────────┘
```

### Deployment Steps

#### 1. Server Setup (Ubuntu 20.04+)
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3.10 python3.10-venv postgresql redis-server nginx

# Create app directory
sudo mkdir -p /opt/chatbot
sudo chown $USER /opt/chatbot
cd /opt/chatbot

# Clone repository
git clone <repo> .
```

#### 2. Python Setup
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

#### 3. Database Setup
```bash
sudo -u postgres psql

postgres=# CREATE DATABASE chatbot_db;
postgres=# CREATE USER chatbot_user WITH PASSWORD 'secure_password_here';
postgres=# GRANT ALL PRIVILEGES ON DATABASE chatbot_db TO chatbot_user;
postgres=# \q
```

#### 4. Configure Application
```bash
# Copy and edit .env
cp .env.example .env
nano .env
# Set:
# - OPENAI_API_KEY (or use free alternative)
# - DATABASE_URL=postgresql://chatbot_user:password@localhost/chatbot_db
# - SECRET_KEY=long_random_string_here
# - DEBUG=False
```

#### 5. Initialize Database
```bash
python app.py  # This creates tables
# Then Ctrl+C to stop
```

#### 6. Gunicorn Configuration
Create `/opt/chatbot/gunicorn.conf.py`:
```python
import multiprocessing

bind = "127.0.0.1:5000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 100
timeout = 30
keepalive = 2
```

#### 7. Nginx Configuration
Create `/etc/nginx/sites-available/chatbot`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

#### 8. Systemd Service
Create `/etc/systemd/system/chatbot.service`:
```ini
[Unit]
Description=AI Chatbot SaaS
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/chatbot
Environment="PATH=/opt/chatbot/venv/bin"
ExecStart=/opt/chatbot/venv/bin/gunicorn \
    --config gunicorn.conf.py \
    --access-logfile /var/log/chatbot/access.log \
    --error-logfile /var/log/chatbot/error.log \
    app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable chatbot
sudo systemctl start chatbot
sudo systemctl status chatbot
```

#### 9. SSL Certificate (Let's Encrypt)
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com
```

---

## Monitoring & Maintenance

### Logs
```bash
# Application logs
sudo journalctl -u chatbot -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Application error logs
tail -f /var/log/chatbot/error.log
```

### Database Backups
```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/chatbot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump chatbot_db | gzip > $BACKUP_DIR/chatbot_$TIMESTAMP.sql.gz

# Keep last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
```

### Health Checks
```bash
# Check API status
curl https://your-domain.com/admin/api/health

# Check database connection
python -c "from app import app, db; app.app_context().push(); print(db.engine.execute('SELECT 1'))"
```

---

## Scaling Considerations

### Horizontal Scaling
1. Use load balancer (HAProxy, AWS ALB)
2. Run multiple Gunicorn instances
3. Use shared database (PostgreSQL)
4. Share session store (Redis)
5. Use CDN for static assets

### Caching Strategy
- Enable Redis for session storage
- Cache LLM responses for common queries
- Use ChromaDB for semantic search caching

### Database Optimization
- Add indexes on frequently queried columns
- Use connection pooling (pgBouncer)
- Implement query logging and monitoring

---

## Free Tier LLM Options

Since OpenAI requires billing, alternatives for development:

### Option 1: OpenRouter (Recommended)
```bash
# In .env
OPENROUTER_API_KEY=your_key_here
# Uses models: Mistral, Claude 3.5 Sonnet, Llama 2, etc.
```

### Option 2: Google Gemini (Free Tier)
```bash
# In .env
GOOGLE_API_KEY=your_key_here
# Uses Gemini 1.5 Flash (generous free tier)
```

### Option 3: Hugging Face (Always Free)
```bash
# In .env
HF_API_KEY=your_key_here
# Uses community models (rate limited but always available)
```

---

## Support & Issues

- Check application logs: `systemctl status chatbot`
- Review configuration: `cat .env` (redact sensitive values)
- Verify database: `psql -d chatbot_db -c "\dt"`
- Test LLM: Navigate to admin panel and test intent fallback

---

## Version Info
- **Python**: 3.8+
- **Flask**: 2.3+
- **SQLAlchemy**: 2.0+
- **PostgreSQL**: 12+ (recommended)
- **ChromaDB**: Latest

Last Updated: March 1, 2026
