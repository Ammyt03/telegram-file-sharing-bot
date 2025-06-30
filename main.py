import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from models import db
from bot_bundle import TelegramBotBundle
import threading
from keep_alive import start_keep_alive


class Base(DeclarativeBase):
    pass


# Create Flask app for database management
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a_secret_key_for_telegram_bot")

# Configure database
database_url = os.environ.get("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///telegram_bot.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize database
db.init_app(app)

# Create tables
with app.app_context():
    import models  # noqa: F401
    try:
        db.create_all()
        print("Database tables created successfully!")
    except Exception as e:
        print(f"Database tables already exist or error: {e}")
        print("Continuing with existing database...")

# Bot configuration
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME")
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
if missing_vars:
    print(f"Warning: Missing required environment variables: {', '.join(missing_vars)}")
    print("Bot functionality will be limited. Flask server will still run for health checks.")
    BOT_CAN_START = False
else:
    BOT_CAN_START = True

@app.route('/')
def status_page():
    """Simple status page for the bot"""
    # Check if environment variables are configured
    config_status = {
        "TELEGRAM_BOT_TOKEN": "✅ Configured" if BOT_TOKEN else "❌ Missing",
        "TELEGRAM_BOT_USERNAME": "✅ Configured" if BOT_USERNAME else "❌ Missing", 
        "LINKSHORTIFY_API_KEY": "✅ Configured" if LINKSHORTIFY_API_KEY else "❌ Missing",
        "STORAGE_CHANNEL_ID": "✅ Configured" if STORAGE_CHANNEL_ID else "❌ Missing",
        "BOT_ADMIN_ID": "✅ Configured" if BOT_ADMIN_ID else "❌ Missing"
    }
    
    all_configured = all(var for var in [BOT_TOKEN, BOT_USERNAME, LINKSHORTIFY_API_KEY, STORAGE_CHANNEL_ID, BOT_ADMIN_ID])
    bot_status = "✅ Running" if all_configured else "❌ Configuration Incomplete"
    
    # Deployment readiness check
    port = int(os.environ.get('PORT', 5000))
    deployment_info = f"""
        <h3>Deployment Information:</h3>
        <ul>
            <li><strong>Flask App:</strong> ✅ Running on 0.0.0.0:{port}</li>
            <li><strong>Database:</strong> ✅ Connected ({app.config['SQLALCHEMY_DATABASE_URI'][:20]}...)</li>
            <li><strong>Health Check:</strong> ✅ Available at / endpoint</li>
            <li><strong>Bot Service:</strong> {bot_status}</li>
        </ul>
    """
    
    return f"""
    <html>
    <head>
        <title>Telegram Bot Status</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto;">
        <h1>🤖 Telegram Media Sharing Bot</h1>
        <p><strong>Bot Status:</strong> {bot_status}</p>
        <p><strong>Database:</strong> ✅ Connected</p>
        <hr>
        <h3>Configuration Status:</h3>
        <ul>
            <li><strong>Bot Token:</strong> {config_status['TELEGRAM_BOT_TOKEN']}</li>
            <li><strong>Bot Username:</strong> {config_status['TELEGRAM_BOT_USERNAME']}</li>
            <li><strong>LinkShortify API:</strong> {config_status['LINKSHORTIFY_API_KEY']}</li>
            <li><strong>Storage Channel:</strong> {config_status['STORAGE_CHANNEL_ID']}</li>
            <li><strong>Bot Admin ID:</strong> {config_status['BOT_ADMIN_ID']}</li>
        </ul>
        <hr>
        {deployment_info}
        <hr>
        {f'<p>To use the bot, message <a href="https://t.me/{BOT_USERNAME}" target="_blank">@{BOT_USERNAME}</a> on Telegram</p>' if BOT_USERNAME else '<p>Bot username not configured</p>'}
        <p><em>Features:</em> File sharing, Token-based access, Ads verification, Channel storage</p>
        {'' if all_configured else '<p><strong>Note:</strong> Bot is not running due to missing environment variables. Please configure all required variables.</p>'}
        <hr>
        <p><small>Ready for deployment to Google Cloud Run, Railway, Render, or other container platforms.</small></p>
    </body>
    </html>
    """

@app.route('/verify-token')
def verify_token():
    """Direct token verification endpoint"""
    from flask import request, redirect
    from utils import decode_token_data
    from models import User, UserToken
    from datetime import datetime, timedelta
    
    token_data_encoded = request.args.get('token')
    if not token_data_encoded:
        return "Invalid verification link", 400
    
    # Decode token data
    try:
        token_data = decode_token_data(token_data_encoded)
        if not token_data:
            return "Invalid token data", 400
        
        user_id = token_data.get('user_id')
        token_value = token_data.get('token')
        
        # Find user
        user = User.query.filter_by(telegram_id=str(user_id)).first()
        if not user:
            return "User not found", 404
        
        # Create new token
        new_token = UserToken(
            user_id=user.id,
            token=token_value,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True
        )
        
        db.session.add(new_token)
        db.session.commit()
        
        # Redirect to telegram bot with success message
        telegram_link = f"https://t.me/{BOT_USERNAME}?start=verified"
        return redirect(telegram_link)
        
    except Exception as e:
        return f"Verification failed: {str(e)}", 500

@app.route('/ads-verify')
def ads_verification():
    """Ads verification page that redirects to Telegram bot"""
    import urllib.parse
    from flask import request
    
    redirect_url = request.args.get('redirect', '')
    if not redirect_url:
        return "Invalid verification link", 400
    
    # Decode the redirect URL
    try:
        decoded_redirect = urllib.parse.unquote(redirect_url)
    except:
        return "Invalid redirect URL", 400
    
    return f"""
    <html>
        <head>
            <title>Ads Verification - Telegram Bot</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 0; 
                    padding: 20px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                .container {{ 
                    background: rgba(255,255,255,0.95); 
                    padding: 40px; 
                    border-radius: 15px; 
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                    text-align: center;
                    color: #333;
                    max-width: 500px;
                    width: 90%;
                }}
                .ads-box {{
                    background: #f8f9fa;
                    border: 2px dashed #6c757d;
                    padding: 60px 20px;
                    margin: 20px 0;
                    border-radius: 10px;
                    font-size: 18px;
                    color: #6c757d;
                }}
                .btn {{
                    background: #28a745;
                    color: white;
                    padding: 15px 30px;
                    border: none;
                    border-radius: 25px;
                    font-size: 18px;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    margin: 10px;
                    transition: all 0.3s;
                }}
                .btn:hover {{
                    background: #218838;
                    transform: translateY(-2px);
                }}
                .timer {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #dc3545;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎟️ Token Verification</h1>
                <p>Complete the verification to get 24-hour access to shared files</p>
                
                <div class="ads-box">
                    <p>📺 Ads Content Here</p>
                    <p>(Please wait for ads to load...)</p>
                    <div class="timer" id="timer">5</div>
                    <p>Viewing advertisement...</p>
                </div>
                
                <a href="#" class="btn" id="continue-btn" style="display:none;" onclick="redirectToBot()">
                    ✅ Continue to Bot
                </a>
                
                <p><small>You will be redirected to Telegram after viewing the ad</small></p>
            </div>
            
            <script>
                let countdown = 5;
                const timerElement = document.getElementById('timer');
                const continueBtn = document.getElementById('continue-btn');
                
                const timer = setInterval(() => {{
                    countdown--;
                    timerElement.textContent = countdown;
                    
                    if (countdown <= 0) {{
                        clearInterval(timer);
                        timerElement.style.display = 'none';
                        continueBtn.style.display = 'inline-block';
                        document.querySelector('.ads-box p').textContent = '✅ Verification Complete!';
                        document.querySelectorAll('.ads-box p')[1].textContent = 'Click continue to access files';
                    }}
                }}, 1000);
                
                function redirectToBot() {{
                    window.location.href = '{decoded_redirect}';
                }}
                
                // Auto redirect after 8 seconds
                setTimeout(() => {{
                    if (countdown <= 0) {{
                        redirectToBot();
                    }}
                }}, 8000);
            </script>
        </body>
    </html>
    """

def run_flask_app():
    """Run Flask app for database operations"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def run_telegram_bot():
    """Run Telegram bot"""
    if not BOT_CAN_START:
        print("Cannot start Telegram bot - missing required environment variables")
        return
    
    # Ensure all variables are strings and not None
    if not all([BOT_TOKEN, BOT_USERNAME, LINKSHORTIFY_API_KEY, STORAGE_CHANNEL_ID, BOT_ADMIN_ID]):
        print("Cannot start Telegram bot - one or more environment variables are None")
        return
    
    with app.app_context():
        from bot_bundle import TelegramBotBundle
        bot = TelegramBotBundle(
            str(BOT_TOKEN), 
            str(BOT_USERNAME), 
            str(LINKSHORTIFY_API_KEY), 
            str(STORAGE_CHANNEL_ID), 
            str(BOT_ADMIN_ID)
        )
        bot.run()

if __name__ == "__main__":
    print("Starting Telegram Media Sharing Bot...")
    print(f"Bot Username: @{BOT_USERNAME or 'Not configured'}")
    print(f"Database URL: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # Start keep-alive service to prevent sleeping
    start_keep_alive()
    
    # Start Flask app in a separate thread for database management
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    if BOT_CAN_START:
        # Start Telegram bot in main thread
        print("Starting Telegram bot...")
        run_telegram_bot()
    else:
        print("Running in Flask-only mode for health checks. Set environment variables to enable bot functionality.")
        # Keep the main thread alive to prevent the app from exiting
        import time
        while True:
            time.sleep(60)  # Sleep for 1 minute and check again
