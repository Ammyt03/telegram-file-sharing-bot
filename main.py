import os
from flask import Flask, request, redirect
from datetime import datetime, timedelta

# Initialize Flask app first
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "telegram_bot_secret_key_2025")

# Configure database
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///telegram_bot.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Import and initialize database from models
from models import db, User, UserToken, MediaFile, FileBundle, AccessLog, init_db
db.init_app(app)

# Create tables
init_db(app)

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
        
        <h3>Deployment Information:</h3>
        <ul>
            <li><strong>Flask App:</strong> ✅ Running on 0.0.0.0:{port}</li>
            <li><strong>Database:</strong> ✅ Connected</li>
            <li><strong>Health Check:</strong> ✅ Available</li>
        </ul>
        
        {f'<p>Bot available at: <a href="https://t.me/{BOT_USERNAME}" target="_blank">@{BOT_USERNAME}</a></p>' if BOT_USERNAME else ''}
        
        {'' if BOT_CAN_START else '<div class="status error"><strong>Note:</strong> Bot cannot start due to missing environment variables.</div>'}
    </body>
    </html>
    """

@app.route('/verify-token')
def verify_token():
    """Token verification endpoint"""
    from utils import decode_token_data
    
    token_data_encoded = request.args.get('token')
    if not token_data_encoded:
        return "Invalid verification link", 400
    
    try:
        token_data = decode_token_data(token_data_encoded)
        if not token_data:
            return "Invalid token data", 400
        
        user_id = token_data.get('user_id')
        token_value = token_data.get('token')
        
        user = User.query.filter_by(telegram_id=str(user_id)).first()
        if not user:
            return "User not found", 404
        
        # Deactivate old tokens
        UserToken.query.filter_by(user_id=user.id, is_active=True).update({"is_active": False})
        
        # Create new token
        new_token = UserToken(
            user_id=user.id,
            token=token_value,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True
        )
        db.session.add(new_token)
        db.session.commit()
        
        # Return success page instead of redirect to provide immediate feedback
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
        return f"Verification failed: {str(e)}", 500

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
    """Start Telegram bot"""
    if not BOT_CAN_START:
        print("Cannot start Telegram bot - missing environment variables")
        return
    
    try:
        from bot_bundle import TelegramBotBundle
        bot = TelegramBotBundle(
            BOT_TOKEN, 
            BOT_USERNAME, 
            LINKSHORTIFY_API_KEY, 
            STORAGE_CHANNEL_ID, 
            BOT_ADMIN_ID
        )
        print(f"Starting Telegram bot @{BOT_USERNAME}...")
        bot.run()
    except Exception as e:
        print(f"Bot startup error: {e}")

def keep_alive():
    """Keep service alive"""
    import threading
    import time
    while True:
        try:
            import requests
            requests.get("http://localhost:5000", timeout=5)
            print("Keep-alive ping successful")
        except:
            pass
        time.sleep(300)

if __name__ == "__main__":
    import threading
    import time
    
    print("=== Starting Telegram Media Sharing Bot ===")
    print(f"Bot Username: @{BOT_USERNAME or 'Not configured'}")
    print(f"Admin ID: {BOT_ADMIN_ID or 'Not configured'}")
    print(f"Database: Connected")
    
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
        print("Starting Telegram bot...")
        run_telegram_bot()
    else:
        print(f"Missing environment variables: {missing_vars}")
        print("Running in Flask-only mode")
        while True:
            time.sleep(60)
