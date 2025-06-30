# Replace the Base class with this:
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Add this after all model definitions:
def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
