from extensions import db
from datetime import datetime

class Gestiune(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    site_code = db.Column(db.String(50))
    default_fuel_type = db.Column(db.String(50), default='Motorină')
    logo_path = db.Column(db.String(200)) # Stores 'static/profile_logos/id.ext'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cui = db.Column(db.String(20))
    address = db.Column(db.String(200))
    product_code = db.Column(db.String(50))
    gestiune_id = db.Column(db.Integer, db.ForeignKey('gestiune.id'), nullable=True) # Temporarily nullable for migration
    
    vehicles = db.relationship('Vehicle', backref='company', lazy=True, order_by='Vehicle.plate_number')
    transactions = db.relationship('Transaction', backref='company', lazy=True)
    
    # Store last generated report interval for convenience
    last_report_start = db.Column(db.DateTime, nullable=True)
    last_report_end = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint('name', 'gestiune_id', name='_company_name_gestiune_uc'),)

    @property
    def color(self):
        # Preferred fixed colors for original companies
        # Normalized lookup
        name_upper = self.name.upper()
        fixed = {
            'TRANSGAT-SORT': 'primary',  # Blue
            'TRANSGAT-SORT SRL': 'primary',
            'VINATI': 'purple',
            'VINATI SRL': 'purple',
            'PETROIL-IMPEX': 'success',  # Green
            'PETROIL-IMPEX SRL': 'success',
            'TRANSGAT-TIR': 'info',      # Cyan
            'TRANSGAT-TIR SRL': 'info',
        }
        if name_upper in fixed:
            return fixed[name_upper]
            
        # Extended palette for others (cyclic based on ID)
        # Removed 'secondary' (gray) as it is reserved for Unallocated
        palette = ['orange', 'teal', 'pink', 'indigo', 'warning', 'danger', 'success', 'info', 'primary']
        
        # Use ID to pick color. If ID is None (not saved yet), default to primary
        if not self.id:
            return 'primary'
            
        # Modulo arithmetic to cycle
        idx = (self.id) % len(palette)
        return palette[idx]
    
    @property
    def color_hex(self):
        """Returns the actual hex color code for inline styles"""
        color_map = {
            'primary': '#0d6efd',
            'success': '#198754',
            'info': '#0dcaf0',
            'warning': '#ffc107',
            'danger': '#dc3545',
            'purple': '#6f42c1',
            'pink': '#d63384',
            'orange': '#fd7e14',
            'teal': '#20c997',
            'indigo': '#6610f2',
            'secondary': '#6c757d',
        }
        return color_map.get(self.color, '#6c757d')


class AppSettings(db.Model):
    """Application settings (per gestiune or global)"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False)
    value = db.Column(db.String(200))
    gestiune_id = db.Column(db.Integer, db.ForeignKey('gestiune.id'), nullable=True)
    
    __table_args__ = (db.UniqueConstraint('key', 'gestiune_id', name='_key_gestiune_uc'),)
    
    @staticmethod
    def get_tank_capacity(gestiune_id=None):
        """Get the total tank capacity in liters for a specific gestiune"""
        query = AppSettings.query.filter_by(key='tank_capacity')
        if gestiune_id:
            query = query.filter_by(gestiune_id=gestiune_id)
        else:
            query = query.filter(AppSettings.gestiune_id == None)
            
        setting = query.first()
        if setting and setting.value:
            try:
                return float(setting.value)
            except:
                return 27000.0  # Default
        return 27000.0
    
    @staticmethod
    def set_tank_capacity(capacity, gestiune_id=None):
        """Set the total tank capacity for a specific gestiune"""
        query = AppSettings.query.filter_by(key='tank_capacity')
        if gestiune_id:
            query = query.filter_by(gestiune_id=gestiune_id)
        else:
            query = query.filter(AppSettings.gestiune_id == None)
            
        setting = query.first()
        if not setting:
            setting = AppSettings(key='tank_capacity', value=str(capacity), gestiune_id=gestiune_id)
            db.session.add(setting)
        else:
            setting.value = str(capacity)
        db.session.commit()


class VehicleCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    icon = db.Column(db.String(50), default='bi-tag-fill')
    gestiune_id = db.Column(db.Integer, db.ForeignKey('gestiune.id'), nullable=True)

    __table_args__ = (db.UniqueConstraint('name', 'gestiune_id', name='_category_name_gestiune_uc'),)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(50), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('vehicle_category.id'), nullable=True)
    gestiune_id = db.Column(db.Integer, db.ForeignKey('gestiune.id'), nullable=True)
    
    category = db.relationship('VehicleCategory', backref=db.backref('vehicles', order_by='Vehicle.plate_number'), lazy=True)
    
    __table_args__ = (db.UniqueConstraint('plate_number', 'gestiune_id', name='_plate_gestiune_uc'),)

class StockOperation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    operation_type = db.Column(db.String(20)) # 'IN' (Refill), 'INITIAL', 'OUT' (Correction)
    quantity = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    gestiune_id = db.Column(db.Integer, db.ForeignKey('gestiune.id'), nullable=True)
    
    company = db.relationship('Company', backref='stock_operations', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id', ondelete='CASCADE'))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    quantity = db.Column(db.Float, nullable=False)
    gestiune_id = db.Column(db.Integer, db.ForeignKey('gestiune.id'), nullable=True)
    
    vehicle = db.relationship('Vehicle', backref='transactions', lazy=True)
    
    # Preventing duplicates within same gestiune
    __table_args__ = (db.UniqueConstraint('date', 'vehicle_id', 'quantity', 'gestiune_id', name='_date_vehicle_qty_gestiune_uc'),)

class HistoryLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50)) # 'StockOperation' or 'Transaction'
    record_id = db.Column(db.Integer)
    action_type = db.Column(db.String(20)) # 'CREATE', 'UPDATE', 'DELETE'
    data_snapshot = db.Column(db.Text) # JSON string of the state (post-update for UPDATE)
    pre_update_snapshot = db.Column(db.Text) # JSON string of pre-update state (for UPDATE actions)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_undone = db.Column(db.Boolean, default=False)
    gestiune_id = db.Column(db.Integer, db.ForeignKey('gestiune.id'), nullable=True)

