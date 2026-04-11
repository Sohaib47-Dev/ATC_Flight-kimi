"""
Backward-compatible entry point: ``python app.py``
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    from app.models import init_db
    from modules.sample_data import populate_sample_data

    init_db(app)
    with app.app_context():
        populate_sample_data()

    app.run(debug=True, host='0.0.0.0', port=5000)
