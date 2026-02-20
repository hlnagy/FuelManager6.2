import os
from flask import Flask
from models import db, Gestiune, Company, StockOperation, Transaction, Vehicle
from extensions import db as db_ext
from sqlalchemy import func

def run_diag():
    app = Flask(__name__)
    db_path = os.path.join(os.environ['LOCALAPPDATA'], 'FuelManager', 'fuel_manager.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db_ext.init_app(app)
    
    with app.app_context():
        # List Gestiuni
        gestiuni = Gestiune.query.all()
        for g in gestiuni:
            print(f"\n=== GESTIUNE ID: {g.id} ({g.name}) ===")
            gid = g.id
            
            # Global Metrics (Old Logic)
            total_consumed = db.session.query(func.sum(Transaction.quantity)).filter_by(gestiune_id=gid).scalar() or 0
            total_initial = db.session.query(func.sum(StockOperation.quantity)).filter_by(gestiune_id=gid, operation_type='INITIAL').scalar() or 0
            total_refill = db.session.query(func.sum(StockOperation.quantity)).filter_by(gestiune_id=gid, operation_type='IN').scalar() or 0
            total_manual_out = db.session.query(func.sum(StockOperation.quantity)).filter_by(gestiune_id=gid, operation_type='OUT').scalar() or 0
            
            # Calculate components
            # 1. Fully allocated transactions
            allocated_trans = db.session.query(func.sum(Transaction.quantity))\
                .join(Vehicle, Transaction.vehicle_id == Vehicle.id)\
                .filter(Transaction.gestiune_id == gid,
                        Transaction.company_id != None,
                        Vehicle.category_id != None).scalar() or 0
            
            # 2. Orphans (Assigned to company but no vehicle/cat)
            orphan_trans = db.session.query(func.sum(Transaction.quantity))\
                .outerjoin(Vehicle, Transaction.vehicle_id == Vehicle.id)\
                .filter(Transaction.gestiune_id == gid,
                        Transaction.company_id != None,
                        db.or_(Transaction.vehicle_id == None, Vehicle.category_id == None)).scalar() or 0
            
            # 3. Direct unallocated (No company)
            direct_unalloc_trans = db.session.query(func.sum(Transaction.quantity))\
                .filter_by(company_id=None, gestiune_id=gid).scalar() or 0
            
            print(f"Total Initial: {total_initial}")
            print(f"Total Refill: {total_refill}")
            print(f"Total Manual Out: {total_manual_out}")
            print(f"Total Consumed (All): {total_consumed}")
            print(f"  - Allocated: {allocated_trans}")
            print(f"  - Orphans: {orphan_trans}")
            print(f"  - Direct Unalloc: {direct_unalloc_trans}")
            
            # Check sum
            calculated_total = (total_initial + total_refill) - (total_manual_out + total_consumed)
            print(f"Calculated Total Stock: {calculated_total}")
            
            # Check individual companies
            companies = Company.query.filter_by(gestiune_id=gid).all()
            total_company_stock = 0
            for c in companies:
                c_initial = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=c.id, gestiune_id=gid, operation_type='INITIAL').scalar() or 0
                c_refill = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=c.id, gestiune_id=gid, operation_type='IN').scalar() or 0
                c_manual_out = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=c.id, gestiune_id=gid, operation_type='OUT').scalar() or 0
                c_consumed = db.session.query(func.sum(Transaction.quantity))\
                    .join(Vehicle, Transaction.vehicle_id == Vehicle.id)\
                    .filter(Transaction.company_id == c.id, 
                            Transaction.gestiune_id == gid,
                            Vehicle.category_id != None).scalar() or 0
                c_current = c_initial + c_refill - c_manual_out - c_consumed
                total_company_stock += c_current
                print(f"  Company {c.name}: {c_current}")
            
            print(f"Total Companies Stock: {total_company_stock}")
            
            # Unallocated balance
            unalloc_initial = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=None, gestiune_id=gid, operation_type='INITIAL').scalar() or 0
            unalloc_in = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=None, gestiune_id=gid, operation_type='IN').scalar() or 0
            unalloc_out = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=None, gestiune_id=gid, operation_type='OUT').scalar() or 0
            unalloc_trans = orphan_trans + direct_unalloc_trans
            
            unalloc_balance = (unalloc_initial + unalloc_in) - (unalloc_out + unalloc_trans)
            print(f"Unallocated Balance: {unalloc_balance}")
            
            print(f"Sum (Company + Unalloc): {total_company_stock + unalloc_balance}")

if __name__ == "__main__":
    run_diag()
