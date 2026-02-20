import os
import sys
from flask import Flask
from models import db, Vehicle, Transaction, Company, Gestiune
from extensions import db as db_ext
from pathlib import Path

# Setup minimal Flask app to use SQLAlchemy
def get_data_dir():
    app_data = os.path.join(os.environ['LOCALAPPDATA'], 'FuelManager')
    if not os.path.exists(app_data):
        os.makedirs(app_data)
    return app_data

app = Flask(__name__)
DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, 'fuel_manager.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db_ext.init_app(app)

def cleanup():
    with app.app_context():
        print(f"Connecting to database at: {DB_PATH}")
        
        # Find TRANSGAT-SORT company in all gestiuni
        transgat_companies = Company.query.filter(Company.name.ilike('TRANSGAT-SORT%')).all()
        if not transgat_companies:
            print("No 'TRANSGAT-SORT' company found. Nothing to clean.")
            return

        company_ids = [c.id for c in transgat_companies]
        print(f"Found {len(company_ids)} company records for 'TRANSGAT-SORT' across all profiles.")

        # 1. Clean Vehicles
        vehicles_to_clean = Vehicle.query.filter(
            Vehicle.company_id.in_(company_ids),
            Vehicle.category_id == None
        ).all()
        
        print(f"Found {len(vehicles_to_clean)} vehicles associated with TRANSGAT-SORT without category.")
        for v in vehicles_to_clean:
            v.company_id = None
        
        # 2. Clean Transactions
        # We also want to clean transactions that were assigned to TRANSGAT-SORT 
        # but the vehicle itself is now unallocated (or was just cleaned)
        transactions_to_clean = Transaction.query.filter(
            Transaction.company_id.in_(company_ids)
        ).all()
        
        cleaned_trans_count = 0
        for t in transactions_to_clean:
            if t.vehicle and (not t.vehicle.company_id or not t.vehicle.category_id):
                t.company_id = None
                cleaned_trans_count += 1
        
        print(f"Cleaned {cleaned_trans_count} transactions.")
        
        db.session.commit()
        print("Cleanup complete.")

if __name__ == "__main__":
    cleanup()
