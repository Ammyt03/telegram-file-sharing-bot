# Replace the database setup section with:
from models import db, init_db

# Initialize database properly
app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///telegram_bot.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

init_db(app)  # Use our new initialization function
