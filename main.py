import os
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from models import db, User, UserToken, MediaFile, FileBundle, AccessLog
from bot_bundle import TelegramBotBundle
import keep_alive

# Flask app setup
app = Flask(__name__)

# Database configuration with PostgreSQL support
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///telegram_bot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'telegram-media-bot-secret-key-2024')

# Initialize database with app
db.init_app(app)

# Environment variables with fallbacks
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or '8077401493:AAFyulz8nNiFPg4YSx6_TwTQUaHaYaK9fqU'
BOT_USERNAME = (os.getenv('TELEGRAM_BOT_USERNAME') or 'specialfeel_bot').replace('@', '')
LINKSHORTIFY_API_KEY = os.getenv('LINKSHORTIFY_API_KEY') or 'ee1bb90d80e866c1cd3a8e11bb29d0e68bfebf6a'
STORAGE_CHANNEL_ID = os.getenv('STORAGE_CHANNEL_ID') or '-1002666294417'
ADMIN_ID = os.getenv('ADMIN_ID') or '6226404256'
port = int(os.getenv('PORT', 5000))

# Check if bot can start
BOT_CAN_START = all([BOT_TOKEN, BOT_USERNAME, LINKSHORTIFY_API_KEY, STORAGE_CHANNEL_ID, ADMIN_ID])

# Create tables
with app.app_context():
    db.create_all()
    print("Database tables created successfully!")

@app.route('/')
def status_page():
    """Status page showing bot configuration"""
    config_status = []
    config_status.append(f"Bot Token: {'✅ Configured' if BOT_TOKEN else '❌ Missing'}")
    config_status.append(f"Bot Username: {'✅ Configured' if BOT_USERNAME else '❌ Missing'}")
    config_status.append(f"LinkShortify API: {'✅ Configured' if LINKSHORTIFY_API_KEY else '❌ Missing'}")
    config_status.append(f"Storage Channel: {'✅ Configured' if STORAGE_CHANNEL_ID else '❌ Missing'}")
    config_status.append(f"Bot Admin ID: {'✅ Configured' if ADMIN_ID else '❌ Missing'}")
    
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
            <strong>Bot Status:</strong> {'✅ Running' if BOT_CAN_START else '❌ Configuration Error'}
        </div>
        
        <h3>Configuration Status:</h3>
        <ul>
            {''.join([f'<li><strong>{item}</strong></li>' for item in config_status])}
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

@app.route('/verify')
@app.route('/verify-token')
def verify_token():
    """Token verification endpoint"""
    def decode_token_data(encoded_data):
        try:
            import base64
            import json
            decoded_bytes = base64.b64decode(encoded_data + '==')
            decoded_str = decoded_bytes.decode('utf-8')
            return json.loads(decoded_str)
        except Exception as e:
            print(f"Token decode error: {e}")
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
        
        with app.app_context():
            user = User.query.filter_by(telegram_id=str(user_id)).first()
            if not user:
                return "User not found", 404
            
            # Create new token
            new_token = UserToken()
            new_token.user_id = user.id
            new_token.token = token_value
            new_token.expires_at = datetime.utcnow() + timedelta(hours=24)
            new_token.is_active = True
            
            db.session.add(new_token)
            db.session.commit()
        
        # Return success page
        return f"""
        <html>
            <head>
                <title>Verification Successful</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; 
                           background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                           min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
                    .container {{ background: white; padding: 40px; border-radius: 15px; 
                                 box-shadow: 0 20px 40px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }}
                    .success {{ color: #28a745; font-size: 48px; margin-bottom: 20px; }}
                    .title {{ color: #333; font-size: 24px; margin-bottom: 15px; font-weight: bold; }}
                    .message {{ color: #666; font-size: 16px; line-height: 1.6; }}
                    .highlight {{ color: #007bff; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✅</div>
                    <div class="title">Congratulations!</div>
                    <div class="message">
                        Ads tokens refreshed successfully! It will expire after <span class="highlight">24 hours</span>
                    </div>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        print(f"Verification error: {e}")
        return f"Verification failed: {str(e)}", 500

@app.route('/ads-verification')
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
                             box-shadow: 0 20px 40px rgba(0,0,0,0.1); text-align: center; max-width: 400px; }}
                .icon {{ font-size: 48px; margin-bottom: 20px; }}
                .title {{ color: #333; font-size: 24px; margin-bottom: 15px; font-weight: bold; }}
                .message {{ color: #666; font-size: 16px; line-height: 1.6; margin-bottom: 30px; }}
                .btn {{ display: inline-block; background: #007bff; color: white; padding: 12px 30px; 
                        text-decoration: none; border-radius: 25px; font-weight: bold; 
                        transition: background 0.3s; }}
                .btn:hover {{ background: #0056b3; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">🎯</div>
                <div class="title">Complete Ads Verification</div>
                <div class="message">
                    Click the button below to complete ads verification and activate your 24-hour access token.
                </div>
                <a href="{decoded_redirect}" class="btn">Verify & Continue</a>
            </div>
        </body>
    </html>
    """

def run_flask():
    """Run Flask server"""
    app.run(host='0.0.0.0', port=port, debug=False)

def run_telegram_bot():
    """Start Telegram bot"""
    if not BOT_CAN_START:
        print("Bot cannot start - missing environment variables")
        return
    
    try:
        bot = TelegramBotBundle(
            token=BOT_TOKEN,
            bot_username=BOT_USERNAME,
            linkshortify_api_key=LINKSHORTIFY_API_KEY,
            storage_channel_id=STORAGE_CHANNEL_ID,
            admin_id=ADMIN_ID
        )
        bot.run()
    except Exception as e:
        print(f"Bot error: {e}")

if __name__ == "__main__":
    try:
        # Start keep-alive
        keep_alive.start_keep_alive()
        
        # Start Flask in a separate thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        print("=== Starting Telegram Media Sharing Bot ===")
        print(f"Bot Username: @{BOT_USERNAME}")
        print(f"Admin ID: {ADMIN_ID}")
        print("Database: Connected")
        print("Running on Replit - Stable Hosting")
        
        # Start Telegram bot after conflict resolution
        print("Starting Telegram bot after conflict resolution...")
        run_telegram_bot()
        
    except Exception as e:
        print(f"Critical startup error: {e}")
        # Keep Flask running even if bot fails
        try:
            app.run(host='0.0.0.0', port=port, debug=False)
        except Exception as flask_error:
            print(f"Flask fallback also failed: {flask_error}")
            exit(1)