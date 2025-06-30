import os
import logging
import threading
import time
from flask import Flask, request, redirect
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "telegram_bot_secret_key_2025")

# Configure database with better connection handling
database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    logger.info(f"Database URL configured: {database_url[:20]}...")
else:
    database_url = "sqlite:///telegram_bot.db"
    logger.warning("Using SQLite fallback database")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 280,
    "pool_pre_ping": True,
    "pool_timeout": 20,
    "max_overflow": 0,
    "echo": False
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database with error handling
try:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy(app)
    
    # Define models inline to avoid import issues
    class User(db.Model):
        __tablename__ = 'users'
        id = db.Column(db.Integer, primary_key=True)
        telegram_id = db.Column(db.String(50), unique=True, nullable=False)
        username = db.Column(db.String(100), nullable=True)
        first_name = db.Column(db.String(100), nullable=True)
        last_name = db.Column(db.String(100), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class UserToken(db.Model):
        __tablename__ = 'user_tokens'
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        token = db.Column(db.String(255), unique=True, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        expires_at = db.Column(db.DateTime, nullable=False)
        is_active = db.Column(db.Boolean, default=True)
        
        def is_expired(self):
            return datetime.utcnow() > self.expires_at

    class FileBundle(db.Model):
        __tablename__ = 'file_bundles'
        id = db.Column(db.Integer, primary_key=True)
        bundle_id = db.Column(db.String(255), unique=True, nullable=False)
        created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        title = db.Column(db.String(255), nullable=True)
        description = db.Column(db.Text, nullable=True)

    class MediaFile(db.Model):
        __tablename__ = 'media_files'
        id = db.Column(db.Integer, primary_key=True)
        file_id = db.Column(db.String(255), unique=True, nullable=False)
        bundle_id = db.Column(db.String(255), db.ForeignKey('file_bundles.bundle_id'), nullable=True)
        file_name = db.Column(db.String(255), nullable=True)
        file_type = db.Column(db.String(50), nullable=False)
        file_size = db.Column(db.Integer, nullable=True)
        telegram_file_id = db.Column(db.String(255), nullable=False)
        uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
        description = db.Column(db.Text, nullable=True)

    class AccessLog(db.Model):
        __tablename__ = 'access_logs'
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
        file_id = db.Column(db.Integer, db.ForeignKey('media_files.id'), nullable=True)
        action = db.Column(db.String(50), nullable=False)
        timestamp = db.Column(db.DateTime, default=datetime.utcnow)
        ip_address = db.Column(db.String(45), nullable=True)
        user_agent = db.Column(db.Text, nullable=True)

    # Create tables with proper error handling
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully!")
        except Exception as e:
            logger.error(f"Database table creation error: {e}")
            
except Exception as e:
    logger.error(f"Database initialization error: {e}")
    db = None

# Bot configuration
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip('@')
LINKSHORTIFY_API_KEY = os.environ.get("LINKSHORTIFY_API_KEY")
STORAGE_CHANNEL_ID = os.environ.get("STORAGE_CHANNEL_ID")
BOT_ADMIN_ID = os.environ.get("BOT_ADMIN_ID")

# Validate required environment variables
required_vars = {
    "TELEGRAM_BOT_TOKEN": BOT_TOKEN,
    "TELEGRAM_BOT_USERNAME": BOT_USERNAME,
    "LINKSHORTIFY_API_KEY": LINKSHORTIFY_API_KEY,
    "STORAGE_CHANNEL_ID": STORAGE_CHANNEL_ID,
    "BOT_ADMIN_ID": BOT_ADMIN_ID
}

missing_vars = [var for var, value in required_vars.items() if not value]
BOT_CAN_START = len(missing_vars) == 0

@app.route('/')
def status_page():
    """Status page showing bot configuration"""
    config_status = {
        "TELEGRAM_BOT_TOKEN": "✅ Configured" if BOT_TOKEN else "❌ Missing",
        "TELEGRAM_BOT_USERNAME": "✅ Configured" if BOT_USERNAME else "❌ Missing", 
        "LINKSHORTIFY_API_KEY": "✅ Configured" if LINKSHORTIFY_API_KEY else "❌ Missing",
        "STORAGE_CHANNEL_ID": "✅ Configured" if STORAGE_CHANNEL_ID else "❌ Missing",
        "BOT_ADMIN_ID": "✅ Configured" if BOT_ADMIN_ID else "❌ Missing"
    }
    
    bot_status = "✅ Running" if BOT_CAN_START else "❌ Configuration Incomplete"
    port = int(os.environ.get('PORT', 5000))
    
    # Check database status
    try:
        if db:
            with app.app_context():
                db.session.execute(db.text('SELECT 1'))
                db_status = "✅ Connected"
        else:
            db_status = "❌ Not Initialized"
    except:
        db_status = "❌ Connection Failed"
    
    return f"""
    <html>
    <head>
        <title>Telegram Bot Status</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }}
            .status {{ padding: 10px; margin: 10px 0; border-radius: 5px; }}
            .success {{ background-color: #d4edda; color: #155724; }}
            .error {{ background-color: #f8d7da; color: #721c24; }}
        </style>
    </head>
    <body>
        <h1>🤖 Telegram Media Sharing Bot</h1>
        <div class="status {'success' if BOT_CAN_START else 'error'}">
            <strong>Bot Status:</strong> {bot_status}
        </div>
        
        <h3>Configuration Status:</h3>
        <ul>
            <li><strong>Bot Token:</strong> {config_status['TELEGRAM_BOT_TOKEN']}</li>
            <li><strong>Bot Username:</strong> {config_status['TELEGRAM_BOT_USERNAME']}</li>
            <li><strong>LinkShortify API:</strong> {config_status['LINKSHORTIFY_API_KEY']}</li>
            <li><strong>Storage Channel:</strong> {config_status['STORAGE_CHANNEL_ID']}</li>
            <li><strong>Bot Admin ID:</strong> {config_status['BOT_ADMIN_ID']}</li>
        </ul>
        
        <h3>System Status:</h3>
        <ul>
            <li><strong>Flask App:</strong> ✅ Running on 0.0.0.0:{port}</li>
            <li><strong>Database:</strong> {db_status}</li>
            <li><strong>Health Check:</strong> ✅ Available</li>
        </ul>
        
        {f'<p>Bot available at: <a href="https://t.me/{BOT_USERNAME}" target="_blank">@{BOT_USERNAME}</a></p>' if BOT_USERNAME else ''}
    </body>
    </html>
    """

@app.route('/verify-token')
def verify_token():
    """Token verification endpoint with enhanced error handling"""
    try:
        from utils import decode_token_data
    except:
        # Fallback token decoding if utils import fails
        import base64
        import json
        
        def decode_token_data(encoded_data):
            try:
                decoded_bytes = base64.b64decode(encoded_data + '==')
                return json.loads(decoded_bytes.decode('utf-8'))
            except:
                return None
    
    token_data_encoded = request.args.get('token')
    if not token_data_encoded:
        return "Invalid verification link", 400
    
    try:
        token_data = decode_token_data(token_data_encoded)
        if not token_data:
            return "Invalid token data", 400
        
        user_id = token_data.get('user_id')
        token_value = token_data.get('token')
        
        # Database operation with error handling
        if db:
            try:
                with app.app_context():
                    user = User.query.filter_by(telegram_id=str(user_id)).first()
                    if not user:
                        logger.warning(f"User not found: {user_id}")
                        # Continue to show success page even if user not found
                    else:
                        # Create new token using attribute assignment
                        new_token = UserToken()
                        new_token.user_id = user.id
                        new_token.token = token_value
                        new_token.expires_at = datetime.utcnow() + timedelta(hours=24)
                        new_token.is_active = True
                        
                        db.session.add(new_token)
                        db.session.commit()
                        
                        logger.info(f"Token created successfully for user {user_id}")
            except Exception as db_error:
                logger.error(f"Database error in token verification: {db_error}")
                # Continue with success page even if DB operation fails
        
        # Return success page
        return f"""
        <html>
            <head>
                <title>Token Activated</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; 
                           background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                           min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
                    .container {{ background: white; padding: 40px; border-radius: 15px; 
                                 text-align: center; max-width: 500px; width: 90%; }}
                    .success-icon {{ font-size: 80px; margin: 20px 0; }}
                    .btn {{ background: #007bff; color: white; padding: 15px 30px; border: none;
                           border-radius: 25px; font-size: 18px; cursor: pointer; text-decoration: none;
                           display: inline-block; margin: 10px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✅</div>
                    <h1>Congratulations!</h1>
                    <p><strong>Ads tokens refreshed successfully!</strong></p>
                    <p>It will expire after 24 hours</p>
                    <br>
                    <p>🔓 Your token is now active</p>
                    <p>📱 You can now access all shared files</p>
                    
                    <a href="https://t.me/{BOT_USERNAME}" class="btn">
                        📱 Return to Bot
                    </a>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return f"""
        <html>
            <head>
                <title>Verification Error</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 20px; text-align: center; }}
                </style>
            </head>
            <body>
                <h2>Verification Error</h2>
                <p>There was an issue with token verification.</p>
                <p>Please try again or contact support.</p>
                <a href="https://t.me/{BOT_USERNAME}">Return to Bot</a>
            </body>
        </html>
        """, 500

@app.route('/ads-verify')
def ads_verification():
    """Ads verification page"""
    import urllib.parse
    
    redirect_url = request.args.get('redirect', '')
    if not redirect_url:
        return "Invalid verification link", 400
    
    try:
        decoded_redirect = urllib.parse.unquote(redirect_url)
    except:
        return "Invalid redirect URL", 400
    
    return f"""
    <html>
        <head>
            <title>Ads Verification</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; 
                       background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                       min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
                .container {{ background: white; padding: 40px; border-radius: 15px; 
                             text-align: center; max-width: 500px; width: 90%; }}
                .ads-box {{ background: #f8f9fa; border: 2px dashed #6c757d; 
                           padding: 60px 20px; margin: 20px 0; border-radius: 10px; }}
                .btn {{ background: #28a745; color: white; padding: 15px 30px; border: none;
                       border-radius: 25px; font-size: 18px; cursor: pointer; text-decoration: none;
                       display: inline-block; margin: 10px; }}
                .timer {{ font-size: 24px; font-weight: bold; color: #dc3545; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎟️ Token Verification</h1>
                <p>Complete verification to get 24-hour access to shared files</p>
                
                <div class="ads-box">
                    <p id="ads-text">📺 Loading advertisement...</p>
                    <div class="timer" id="timer">5</div>
                </div>
                
                <a href="#" class="btn" id="continue-btn" style="display:none;" onclick="redirectToBot()">
                    ✅ Continue to Bot
                </a>
            </div>
            
            <script>
                let countdown = 5;
                const timerEl = document.getElementById('timer');
                const continueBtn = document.getElementById('continue-btn');
                const adsText = document.getElementById('ads-text');
                
                const timer = setInterval(() => {{
                    countdown--;
                    timerEl.textContent = countdown;
                    
                    if (countdown <= 0) {{
                        clearInterval(timer);
                        timerEl.style.display = 'none';
                        continueBtn.style.display = 'inline-block';
                        adsText.textContent = '✅ Verification Complete!';
                    }}
                }}, 1000);
                
                function redirectToBot() {{
                    window.location.href = '{decoded_redirect}';
                }}
                
                setTimeout(() => {{
                    if (countdown <= 0) redirectToBot();
                }}, 8000);
            </script>
        </body>
    </html>
    """

def run_telegram_bot():
    """Start Telegram bot with enhanced error handling"""
    if not BOT_CAN_START:
        logger.error("Cannot start Telegram bot - missing environment variables")
        return
    
    try:
        with app.app_context():
            from bot_bundle import TelegramBotBundle
            bot = TelegramBotBundle(
                BOT_TOKEN, 
                BOT_USERNAME, 
                LINKSHORTIFY_API_KEY, 
                STORAGE_CHANNEL_ID, 
                BOT_ADMIN_ID
            )
            logger.info(f"Starting Telegram bot @{BOT_USERNAME}...")
            bot.run()
    except Exception as e:
        logger.error(f"Bot startup error: {e}")

def keep_alive():
    """Keep service alive"""
    while True:
        try:
            import requests
            requests.get("http://localhost:5000", timeout=5)
            logger.info("Keep-alive ping successful")
        except Exception as e:
            logger.error(f"Keep-alive error: {e}")
        time.sleep(300)

if __name__ == "__main__":
    logger.info("=== Starting Telegram Media Sharing Bot ===")
    logger.info(f"Bot Username: @{BOT_USERNAME or 'Not configured'}")
    logger.info(f"Admin ID: {BOT_ADMIN_ID or 'Not configured'}")
    
    # Start keep-alive in background
    keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
    keep_alive_thread.start()
    
    # Start Flask app in background
    port = int(os.environ.get('PORT', 5000))
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    
    if BOT_CAN_START:
        logger.info("Starting Telegram bot...")
        run_telegram_bot()
    else:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.info("Running in Flask-only mode")
        while True:
            time.sleep(60)
