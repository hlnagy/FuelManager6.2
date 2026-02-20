import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from extensions import db
from datetime import datetime
import pandas as pd
from werkzeug.utils import secure_filename
import shutil
import socket
import time
from pathlib import Path
import json
import uuid
import threading
import signal
import subprocess
import webbrowser
import base64
import re

# --- CONFIGURATION & PATH HELPERS ---

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_data_dir():
    """Get the AppData directory for user data (database, logs, logos)"""
    app_data = os.path.join(os.environ['LOCALAPPDATA'], 'FuelManager')
    if not os.path.exists(app_data):
        os.makedirs(app_data)
    
    # Ensure logs directory exists
    logs_dir = os.path.join(app_data, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        
    # Ensure logos directory exists
    logos_dir = os.path.join(app_data, 'logos')
    if not os.path.exists(logos_dir):
        os.makedirs(logos_dir)
        
    return app_data

def get_instance_path():
    """Returns instance folder path in AppData to avoid Program Files permission issues"""
    appdata = os.getenv('LOCALAPPDATA')
    if not appdata:
        appdata = os.path.expanduser('~/.fuelmanager')
    
    instance_dir = Path(appdata) / 'FuelManager' / 'instance'
    instance_dir.mkdir(parents=True, exist_ok=True)
    return str(instance_dir)

def is_already_running(port=5000):
    """Check if app is already running on the specified port"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('localhost', port))
            return result == 0
    except:
        return False

# --- FLASK APP INIT ---
app = Flask(__name__, 
            template_folder=get_resource_path('templates'), 
            static_folder=get_resource_path('static'),
            instance_path=get_instance_path())

app.secret_key = 'supersecretkey'  # Change this in production!

# --- CONFIGURATION: USE APPDATA ---
DATA_DIR = get_data_dir()
DB_PATH = os.path.join(DATA_DIR, 'fuel_manager.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- GLOBAL STATE FOR HEARTBEAT & AUTO-SHUTDOWN ---
last_heartbeat = time.time()
BUSY_MODE = False

# --- LOGGING SETUP ---
log_file = os.path.join(DATA_DIR, 'logs', 'app.log')
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5),
                        logging.StreamHandler()
                    ])

# Helper for migrations/init
def get_database_path():
    return DB_PATH

db.init_app(app)

# Custom Jinja2 filter for hashing strings to integers
@app.template_filter('hash')
def hash_filter(s):
    """Convert string to hash integer for color selection"""
    return hash(str(s))

# --- Database Migration Logic ---
def run_migrations():
    """Ensure all required columns exist for the multi-profile upgrade"""
    import sqlite3
    db_path = get_database_path()
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List of tables and columns to check/add
    # Format: (table_name, column_name, column_definition)
    migrations = [
        ('gestiune', 'default_fuel_type', "TEXT DEFAULT 'Motorină'"),
        ('gestiune', 'logo_path', "TEXT"),
        ('company', 'gestiune_id', "INTEGER REFERENCES gestiune(id)"),
        ('app_settings', 'gestiune_id', "INTEGER REFERENCES gestiune(id)"),
        ('vehicle_category', 'gestiune_id', "INTEGER REFERENCES gestiune(id)"),
        ('vehicle_category', 'icon', "TEXT DEFAULT 'bi-tag-fill'"),
        ('vehicle', 'gestiune_id', "INTEGER REFERENCES gestiune(id)"),
        ('stock_operation', 'gestiune_id', "INTEGER REFERENCES gestiune(id)"),
        ('transaction', 'gestiune_id', "INTEGER REFERENCES gestiune(id)"),
        ('history_log', 'gestiune_id', "INTEGER REFERENCES gestiune(id)"),
        ('history_log', 'pre_update_snapshot', "TEXT"),
        ('company', 'last_report_start', "TIMESTAMP"),
        ('company', 'last_report_end', "TIMESTAMP"),
    ]
    
    try:
        # 1. Create app_settings if it doesn't exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_settings'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE app_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key VARCHAR(50) NOT NULL,
                    value VARCHAR(200),
                    gestiune_id INTEGER REFERENCES gestiune(id),
                    UNIQUE(key, gestiune_id)
                )
            """)
            conn.commit()
            print("Migration: Created app_settings table with composite unique constraint")
        else:
            # Table exists, check if it has the old single-column unique constraint on 'key'
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='app_settings'")
            create_sql = cursor.fetchone()[0]
            if 'key" UNIQUE' in create_sql or 'key VARCHAR(50) UNIQUE' in create_sql:
                print("Migration: Detected old UNIQUE constraint on app_settings. Performing table migration...")
                # SQLite doesn't support ALTER TABLE DROP CONSTRAINT, so we must recreate
                cursor.executescript("""
                    BEGIN;
                    ALTER TABLE app_settings RENAME TO app_settings_old;
                    CREATE TABLE app_settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key VARCHAR(50) NOT NULL,
                        value VARCHAR(200),
                        gestiune_id INTEGER REFERENCES gestiune(id),
                        UNIQUE(key, gestiune_id)
                    );
                    INSERT INTO app_settings (id, key, value, gestiune_id)
                    SELECT id, key, value, gestiune_id FROM app_settings_old;
                    DROP TABLE app_settings_old;
                    COMMIT;
                """)
                print("Migration: app_settings table migration complete.")

        # 2. Add columns if missing
        for table, column, definition in migrations:
            cursor.execute(f"PRAGMA table_info([{table}])")
            columns = [info[1] for info in cursor.fetchall()]
            if columns and column not in columns:
                try:
                    cursor.execute(f"ALTER TABLE [{table}] ADD COLUMN [{column}] {definition}")
                    conn.commit()
                    print(f"Migration: Added {column} to {table}")
                except Exception as e:
                    print(f"Migration Error on {table}.{column}: {e}")
                    
    except Exception as e:
        print(f"Migration fatal error: {e}")
    finally:
        conn.close()

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/usercontent/<path:filename>')
def user_content(filename):
    """Serve user files (logos) from AppData"""
    return send_from_directory(os.path.join(DATA_DIR, 'logos'), filename)

# --- INITIALIZATION LOGIC ---
def init_profiles():
    """Ensure DB structure exists"""
    with app.app_context():
        # IMPORT MODELS HERE to ensure they are registered with SQLAlchemy before create_all
        import models 
        
        # ALWAYS run migrations first to patch schema if it exists but is old
        run_migrations()
        
        # Create tables if they don't exist
        db.create_all()
        # No longer creating default profile automatically!
        # This forces the user to go through the Setup flow.

# Run migrations/init immediately
def migrate_existing_logos():
    """Move logos from static folder to AppData logos folder for persistence"""
    static_logos_dir = os.path.join(app.root_path, 'static')
    data_logos_dir = os.path.join(DATA_DIR, 'logos')
    
    # Paths to migrate
    subfolders = ['profile_logos', 'company_logos']
    
    for sub in subfolders:
        old_dir = os.path.join(static_logos_dir, sub)
        new_dir = os.path.join(data_logos_dir, sub)
        
        if not os.path.exists(new_dir):
            os.makedirs(new_dir)
            
        if os.path.exists(old_dir):
            for filename in os.listdir(old_dir):
                old_file = os.path.join(old_dir, filename)
                new_file = os.path.join(new_dir, filename)
                
                if os.path.isfile(old_file) and not os.path.exists(new_file):
                    try:
                        shutil.copy2(old_file, new_file)
                        logging.info(f"Migrated logo: {sub}/{filename}")
                    except Exception as e:
                        logging.error(f"Error migrating {filename}: {e}")

init_profiles()
migrate_existing_logos()

@app.before_request
def enforce_profile():
    # List of allowed endpoints during setup/login
    allowed = ['setup_page', 'setup_create', 'setup_restore', 'user_content', 'static', 'select_profile_page', 'select_profile_action', 'login', 'shutdown', 'heartbeat']
    
    # 1. Check if DB is empty (Fresh Install)
    # We do this check only if we are not already in the setup flow
    if request.endpoint not in allowed:
        try:
            from models import Gestiune
            if Gestiune.query.count() == 0:
                return redirect(url_for('setup_page'))
        except:
            # DB might not exist yet
            return redirect(url_for('setup_page'))

        if 'gestiune_id' not in session:
            return redirect(url_for('select_profile_page'))

@app.context_processor
def inject_globals():
    return dict(
        desktop_mode=os.environ.get('DESKTOP_MODE') == '1'
    )

# --- SETUP ROUTES ---
@app.route('/setup')
def setup_page():
    return render_template('setup.html')

@app.route('/setup/create', methods=['POST'])
def setup_create():
    from models import Gestiune
    name = request.form['name']
    site_code = request.form.get('site_code')
    
    # Create first profile
    gest = Gestiune(name=name, site_code=site_code, default_fuel_type='Motorină')
    db.session.add(gest)
    db.session.commit()
    
    # Auto-login
    session['gestiune_id'] = gest.id
    session.permanent = True
    
    flash(f'Bun venit! Profilul "{name}" a fost creat.', 'success')
    return redirect('/')

@app.route('/setup/restore', methods=['POST'])
def setup_restore():
    print("DEBUG: Entered setup_restore")
    global BUSY_MODE
    try:
        if 'database_file' not in request.files:
            flash('Niciun fișier selectat.', 'danger')
            return redirect('/setup')
            
        file = request.files['database_file']
        if file.filename == '':
            flash('Niciun fișier selectat.', 'danger')
            return redirect('/setup')
            
        if file:
            # Validate SQLite Header
            print("DEBUG: Check file header")
            header = file.read(16)
            file.seek(0) # Reset cursor
            if header != b'SQLite format 3\x00':
                flash('Fișierul încărcat nu este o bază de date validă (SQLite).', 'danger')
                return redirect('/setup')
                
            # SAFE RESTORE Logic
            BUSY_MODE = True
            print("DEBUG: BUSY_MODE set to True")
            
            backup_path = DB_PATH + '.bak'
            has_backup = False
            
            try:
                # 1. Close connection and dispose engine to release file lock
                print("DEBUG: Closing DB connections")
                db.session.remove()
                db.engine.dispose()
                time.sleep(0.5) # Give OS a moment to release handle
                
                # 2. Create Backup IF DB exists
                if os.path.exists(DB_PATH):
                    print("DEBUG: Creating backup")
                    # Retry loop for renaming in case of lingering locks
                    import gc
                    gc.collect() # Force GC to release SQL handles
                    
                    chk = 0
                    while chk < 5:
                        try:
                            if os.path.exists(DB_PATH):
                                if os.path.exists(backup_path):
                                    os.remove(backup_path)
                                os.rename(DB_PATH, backup_path)
                            has_backup = True # Only set if rename succeeded
                            break
                        except PermissionError:
                            print(f"DEBUG: PermissionError retry {chk}")
                            chk += 1
                            time.sleep(1)
                            if chk == 5: raise
                
                # 3. Save New File
                print(f"DEBUG: Saving new file to {DB_PATH}")
                file.save(DB_PATH)
                
                # 4. Run Migrations & Repair Schema
                print("DEBUG: Repairing schema")
                try:
                    # Force creation of missing tables (like 'gestiune' in old backups)
                    with app.app_context():
                        # IMPORTANT: Import models to register tables with SQLAlchemy
                        import models
                        db.create_all()
                        
                    # Run column-level migrations
                    run_migrations()
                    
                    # 5. Legacy Data Migration (if key tables are empty)
                    # If we restored an old DB, 'gestiune' table might be empty but 'company' has data
                    from models import Gestiune, Company, Vehicle
                    if Gestiune.query.count() == 0:
                        print("DEBUG: Detected Legacy DB (No Gestiune). Migrating...")
                        # Create default profile
                        default_gest = Gestiune(name='Transgat-Sort (Migrat)', site_code='LEGACY', default_fuel_type='Motorină')
                        db.session.add(default_gest)
                        db.session.commit()
                        
                        # Assign all orphaned records to this profile
                        print("DEBUG: Assigning legacy records to default profile")
                        Company.query.filter(Company.gestiune_id == None).update({Company.gestiune_id: default_gest.id}, synchronize_session=False)
                        Vehicle.query.filter(Vehicle.gestiune_id == None).update({Vehicle.gestiune_id: default_gest.id}, synchronize_session=False)
                        
                        # Also update stock/transactions if possible (assuming models exists)
                        try:
                            from models import StockOperation, Transaction
                            StockOperation.query.filter(StockOperation.gestiune_id == None).update({StockOperation.gestiune_id: default_gest.id}, synchronize_session=False)
                            Transaction.query.filter(Transaction.gestiune_id == None).update({Transaction.gestiune_id: default_gest.id}, synchronize_session=False)
                        except:
                            pass
                            
                        db.session.commit()
                        print("DEBUG: Legacy migration complete")
                        
                except Exception as e:
                    raise Exception(f"Migrarea a eșuat: {e}")
                
                # 6. Success
                BUSY_MODE = False
                flash('Baza de date a fost restaurată cu succes! Vă rugăm să selectați o gestiune.', 'success')
                print("DEBUG: Success, redirecting")
                return redirect(url_for('select_profile_page'))
                
            except Exception as e:
                BUSY_MODE = False
                print(f"DEBUG: Exception inner: {e}")
                # ROLLBACK
                if has_backup:
                    print("DEBUG: Rolling back")
                    if os.path.exists(DB_PATH):
                        try:
                            os.remove(DB_PATH)
                        except:
                            pass
                    try:
                        os.rename(backup_path, DB_PATH) # Restore original
                    except:
                        pass
                    flash(f'Restaurare eșuată. Baza de date a fost revenită la starea anterioară. Hiba: {e}', 'danger')
                else:
                    # New installation: failed to restore, just clean up corrupt attempt
                    print("DEBUG: Cleanup new install")
                    if os.path.exists(DB_PATH):
                        try:
                            os.remove(DB_PATH)
                        except:
                            pass
                    flash(f'Restaurare eșuată pe un sistem nou. Fișierul a fost eliminat. Hiba: {e}', 'danger')
                     
                return redirect('/setup')
    except Exception as e:
        BUSY_MODE = False
        import traceback
        traceback.print_exc()
        flash(f'CRITICAL ERROR: {str(e)}', 'danger')
        return redirect('/setup')
            
    return redirect('/setup')

@app.context_processor
def inject_gestiune():
    try:
        from models import Gestiune
        gid = session.get('gestiune_id')
        context = {'get_db_path': get_database_path}
        
        # Guard against DB errors during context injection
        if gid:
            try:
                from models import AppSettings
                gestiune = Gestiune.query.get(gid)
                context['active_gestiune'] = gestiune
                
                # Fetch saved theme
                theme_setting = AppSettings.query.filter_by(key='app_theme', gestiune_id=gid).first()
                context['current_theme'] = theme_setting.value if theme_setting else 'light'
            except:
                context['active_gestiune'] = None
                context['current_theme'] = 'light'
        else:
            context['active_gestiune'] = None
            context['current_theme'] = 'light'
        return context
    except Exception as e:
        # Fallback if everything fails (e.g. DB locked)
        print(f"DEBUG: Context Processor Error: {e}")
        return {'active_gestiune': None, 'get_db_path': get_database_path}

@app.route('/select-profile')
def select_profile_page():
    from models import Gestiune
    profiles = Gestiune.query.all()
    return render_template('select_profile.html', profiles=profiles)

@app.route('/select-profile/<int:id>')
def select_profile_action(id):
    from models import Gestiune
    gest = Gestiune.query.get_or_404(id)
    session['gestiune_id'] = gest.id
    session.permanent = True
    flash(f"Gestiune activă: {gest.name}", "success")
    return redirect('/')

@app.route('/admin/profiles')
def profile_management():
    # Deprecated, redirect to new management interface
    return redirect(url_for('select_profile_page'))

@app.route('/admin/profile/new', methods=['POST'])
def new_profile():
    print("DEBUG: new_profile route called")  # DEBUG
    from models import Gestiune
    from sqlalchemy.exc import IntegrityError
    
    name = request.form['name']
    site_code = request.form.get('site_code')
    fuel_type = request.form.get('fuel_type', 'Motorină')
    
    print(f"DEBUG: Attempting to create profile: name={name}, site_code={site_code}, fuel_type={fuel_type}")  # DEBUG
    
    # Check if profile with this name already exists
    existing = Gestiune.query.filter_by(name=name).first()
    if existing:
        flash(f'Există deja o gestiune cu numele "{name}". Alegeți un alt nume.', 'danger')
        return redirect(url_for('select_profile_page'))
    
    try:
        gest = Gestiune(name=name, site_code=site_code, default_fuel_type=fuel_type)
        db.session.add(gest)
        db.session.commit()
        
        # Handle Logo Upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                try:
                    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
                    if ext in ['png', 'jpg', 'jpeg']:
                        if ext == 'jpeg': ext = 'jpg'
                        
                        # Ensure subfolder exists in AppData
                        save_dir = os.path.join(DATA_DIR, 'logos', 'profile_logos')
                        if not os.path.exists(save_dir):
                            os.makedirs(save_dir)
                            
                        save_path = os.path.join(save_dir, f"{gest.id}.{ext}")
                        file.save(save_path)
                        gest.logo_path = f"profile_logos/{gest.id}.{ext}"
                        db.session.commit()
                except Exception as e:
                    flash(f"Eroare salvare logo: {str(e)}", "warning")

        flash("Profil nou creat cu succes!", "success")
        return redirect(url_for('select_profile_page'))
        
    except IntegrityError as e:
        db.session.rollback()
        flash(f'Eroare la crearea profilului: Numele "{name}" este deja folosit. Alegeți un alt nume.', 'danger')
        return redirect(url_for('select_profile_page'))
    except Exception as e:
        db.session.rollback()
        flash(f'Eroare la crearea profilului: {str(e)}', 'danger')
        return redirect(url_for('select_profile_page'))

@app.route('/admin/profile/edit/<int:id>', methods=['POST'])
def edit_profile(id):
    from models import Gestiune
    gest = Gestiune.query.get_or_404(id)
    gest.name = request.form['name']
    gest.site_code = request.form.get('site_code')
    gest.default_fuel_type = request.form.get('fuel_type')
    
    # Handle Logo Upload
    if 'logo' in request.files:
        file = request.files['logo']
        if file and file.filename != '':
            try:
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
                if ext in ['png', 'jpg', 'jpeg']:
                    if ext == 'jpeg': ext = 'jpg'
                    
                    # Ensure subfolder exists in AppData
                    save_dir = os.path.join(DATA_DIR, 'logos', 'profile_logos')
                    if not os.path.exists(save_dir):
                        os.makedirs(save_dir)
                    
                    # Clean old in AppData
                    for old_ext in ['png', 'jpg']:
                        old_path = os.path.join(save_dir, f"{gest.id}.{old_ext}")
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    
                    save_path = os.path.join(save_dir, f"{gest.id}.{ext}")
                    file.save(save_path)
                    gest.logo_path = f"profile_logos/{gest.id}.{ext}"
            except Exception as e:
                flash(f"Eroare salvare logo: {str(e)}", "warning")

    db.session.commit()
    flash("Modificări salvate!", "success")
    return redirect(url_for('select_profile_page'))

@app.route('/admin/profile/delete_logo/<int:id>')
def delete_profile_logo(id):
    from models import Gestiune
    gest = Gestiune.query.get_or_404(id)
    if gest.logo_path:
        path = os.path.join(DATA_DIR, 'logos', gest.logo_path)
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
        gest.logo_path = None
        db.session.commit()
        flash('Logo-ul a fost șters.', 'success')
    return redirect(url_for('select_profile_page'))

@app.route('/admin/profile/delete/<int:id>')
def delete_profile(id):
    from models import Gestiune, Company, Vehicle, Transaction, StockOperation, VehicleCategory
    gest = Gestiune.query.get_or_404(id)
    
    # Settle session if deleted profile was active
    if session.get('gestiune_id') == id:
        session.pop('gestiune_id', None)
        
    # Delete all associated data
    Transaction.query.filter_by(gestiune_id=id).delete()
    StockOperation.query.filter_by(gestiune_id=id).delete()
    Vehicle.query.filter_by(gestiune_id=id).delete()
    VehicleCategory.query.filter_by(gestiune_id=id).delete()
    Company.query.filter_by(gestiune_id=id).delete()
    
    db.session.delete(gest)
    db.session.commit()
    flash("Gestiune și toate datele asociate au fost șterse.", "warning")
    return redirect(url_for('select_profile_page'))

@app.route('/machines')
def machine_categories():
    from models import VehicleCategory, Transaction, Vehicle
    from sqlalchemy import func
    gid = session.get('gestiune_id')
    categories = VehicleCategory.query.filter_by(gestiune_id=gid).order_by(VehicleCategory.name).all()
    
    # Attach data to each category
    for cat in categories:
        # Get last 100 transactions
        cat.recent_transactions = Transaction.query.filter_by(gestiune_id=gid).join(Vehicle).filter(Vehicle.category_id == cat.id).order_by(Transaction.date.desc()).limit(100).all()
        # Calculate totals
        cat.total_qty = db.session.query(func.sum(Transaction.quantity)).filter(Transaction.gestiune_id == gid).join(Vehicle).filter(Vehicle.category_id == cat.id).scalar() or 0
        cat.vehicle_count = len(cat.vehicles)
        
    return render_template('machine_categories.html', categories=categories)
@app.route('/')
def dashboard():
    from models import Company, StockOperation, Transaction
    from sqlalchemy import func
    from models import AppSettings
    
    gid = session.get('gestiune_id')
    
    # Get global tank capacity for this gestiune
    tank_capacity = AppSettings.get_tank_capacity(gid)
    
    # Calculate stock per company
    companies = Company.query.filter_by(gestiune_id=gid).all()
    stocks = {}
    
    for c in companies:
        initial = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=c.id, gestiune_id=gid, operation_type='INITIAL').scalar() or 0
        refill = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=c.id, gestiune_id=gid, operation_type='IN').scalar() or 0
        manual_out = db.session.query(func.sum(StockOperation.quantity)).filter_by(company_id=c.id, gestiune_id=gid, operation_type='OUT').scalar() or 0
        # Consumed calculation: Exclude transactions that are considered "unallocated" (no vehicle or no category)
        # We need to join with Vehicle to check category_id
        from models import Vehicle
        consumed = db.session.query(func.sum(Transaction.quantity))\
            .join(Vehicle, Transaction.vehicle_id == Vehicle.id)\
            .filter(Transaction.company_id == c.id, 
                    Transaction.gestiune_id == gid,
                    Vehicle.category_id != None).scalar() or 0
        
        current = initial + refill - manual_out - consumed
        
        # Calculate last update from both Transactions AND Stock Operations
        last_trans_date = db.session.query(func.max(Transaction.date)).filter_by(company_id=c.id, gestiune_id=gid).scalar()
        last_op_date = db.session.query(func.max(StockOperation.date)).filter_by(company_id=c.id, gestiune_id=gid).scalar()
        
        dates = [d for d in [last_trans_date, last_op_date] if d]
        last_update = max(dates) if dates else None
        
        stocks[c.id] = {
            'name': c.name,
            'initial': initial,
            'refill': refill,
            'consumed': consumed + manual_out,
            'current': current,
            'color': c.color,
            'color_hex': c.color_hex,
            'last_update': last_update
        }

        # Check for custom logo in AppData (PNG or JPG)
        logo_dir = os.path.join(DATA_DIR, 'logos', 'company_logos')
        logo_path_png = os.path.join(logo_dir, f"{c.id}.png")
        logo_path_jpg = os.path.join(logo_dir, f"{c.id}.jpg")
        
        if os.path.exists(logo_path_png):
            stocks[c.id]['logo_url'] = url_for('user_content', filename=f"company_logos/{c.id}.png")
        elif os.path.exists(logo_path_jpg):
            stocks[c.id]['logo_url'] = url_for('user_content', filename=f"company_logos/{c.id}.jpg")
        else:
            stocks[c.id]['logo_url'] = None
        
    # Add "Alimentari nealocate" (Unallocated refuels) card
    # Combined Stats
    # 1. Unallocated Transactions (No company OR No vehicle OR No category)
    from models import Vehicle
    unalloc_trans_direct = db.session.query(func.sum(Transaction.quantity)).filter_by(company_id=None, gestiune_id=gid).scalar() or 0
    
    # 2. Transactions assigned to a company but missing vehicle/category
    unalloc_trans_orphans = db.session.query(func.sum(Transaction.quantity))\
        .outerjoin(Vehicle, Transaction.vehicle_id == Vehicle.id)\
        .filter(Transaction.gestiune_id == gid,
                Transaction.company_id != None,
                db.or_(Transaction.vehicle_id == None, Vehicle.category_id == None)).scalar() or 0
    
    unalloc_trans_qty = unalloc_trans_direct + unalloc_trans_orphans
    unalloc_trans_count = Transaction.query.outerjoin(Vehicle, Transaction.vehicle_id == Vehicle.id)\
        .filter(Transaction.gestiune_id == gid,
                db.or_(Transaction.company_id == None, Transaction.vehicle_id == None, Vehicle.category_id == None)).count()
    
    unalloc_trans_last = db.session.query(func.max(Transaction.date)).outerjoin(Vehicle, Transaction.vehicle_id == Vehicle.id)\
        .filter(Transaction.gestiune_id == gid,
                db.or_(Transaction.company_id == None, Transaction.vehicle_id == None, Vehicle.category_id == None)).scalar()

    # 3. Unallocated Stock Operations (ONLY Manual Out 'OUT', not Refills 'IN')
    unalloc_ops_qty = db.session.query(func.sum(StockOperation.quantity))\
        .filter_by(company_id=None, gestiune_id=gid, operation_type='OUT').scalar() or 0
    unalloc_ops_count = StockOperation.query.filter_by(company_id=None, gestiune_id=gid, operation_type='OUT').count()
    unalloc_ops_last = db.session.query(func.max(StockOperation.date))\
        .filter_by(company_id=None, gestiune_id=gid, operation_type='OUT').scalar()
    
    unallocated_consumed = unalloc_trans_qty + unalloc_ops_qty
    unallocated_count = unalloc_trans_count + unalloc_ops_count
    
    from sqlalchemy import or_
    dates = [d for d in [unalloc_trans_last, unalloc_ops_last] if d]
    unallocated_last_update = max(dates) if dates else None
    
    # Combined Stats
    # ACCOUNTING TOTAL: Sum up all company stocks to get global available balance
    total_stock = sum(s['current'] for s in stocks.values())
    
    # Calculate global metrics based on accounting total
    total_percent = (total_stock / tank_capacity * 100) if tank_capacity > 0 else 0
    
    # Check if overloaded
    is_overloaded = total_stock > tank_capacity
    overload_qty = total_stock - tank_capacity if is_overloaded else 0
    
    # Keep display percentage at 100% max
    display_percent = min(total_percent, 100)
    
    free_space = tank_capacity - total_stock
    if free_space < 0: free_space = 0

    # Calculate global last update (Any activity: In, Out, Trans)
    last_op = db.session.query(func.max(StockOperation.date)).filter_by(gestiune_id=gid).scalar()
    last_trans = db.session.query(func.max(Transaction.date)).filter_by(gestiune_id=gid).scalar()
    
    dates = [d for d in [last_op, last_trans] if d]
    last_event = max(dates) if dates else None
    
    return render_template('dashboard.html', 
                          stocks=stocks, 
                          companies=companies, 
                          total_stock=total_stock, 
                          tank_capacity=tank_capacity,
                          total_percent=total_percent,
                          display_percent=display_percent,
                          free_space=free_space,
                          last_update=last_event,
                          is_overloaded=is_overloaded,
                          overload_qty=overload_qty,
                          unallocated_consumed=unallocated_consumed,
                          unallocated_count=unallocated_count,
                          unallocated_last_update=unallocated_last_update)

@app.route('/admin/set_tank_capacity', methods=['POST'])
def set_tank_capacity():
    from models import AppSettings
    gid = session.get('gestiune_id')
    try:
        new_capacity = float(request.form.get('capacity', 27000))
        AppSettings.set_tank_capacity(new_capacity, gid)
        flash(f'Capacitatea bazinului a fost actualizată la {new_capacity:,.0f} L!', 'success')
    except Exception as e:
        flash(f'Eroare la actualizarea capacității: {str(e)}', 'danger')
    
    return redirect('/')

@app.route('/admin/company/set_capacity/<int:company_id>', methods=['POST'])
def set_company_capacity(company_id):
    gid = session.get('gestiune_id')
    c = Company.query.filter_by(id=company_id, gestiune_id=gid).first_or_404()
    try:
        new_capacity = float(request.form.get('capacity', 0))
        c.capacity = new_capacity
        db.session.commit()
        flash(f'Capacitatea bazinului pentru {c.name} a fost actualizată!', 'success')
    except Exception as e:
        flash(f'Eroare la actualizarea capacității: {str(e)}', 'danger')
    
    return redirect('/')

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.template_filter('format_thousands')
def format_thousands(value, decimals=0):
    try:
        val = float(value)
        if decimals > 0:
            fmt = "{:,.%df}" % decimals
            # First replace thousands comma with space, then replace decimal dot with comma
            return fmt.format(val).replace(",", " ").replace(".", ",")
        else:
            return "{:,}".format(int(val)).replace(",", " ")
    except (ValueError, TypeError):
        return value

@app.route('/data-management')
def data_management():
    return render_template('data_management.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    from services import process_csv_import
    from models import Transaction, Vehicle, Company
    import os
    
    gid = session.get('gestiune_id')
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Niciun fișier selectat', 'danger')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('Niciun fișier selectat', 'danger')
            return redirect(request.url)
            
        if file:
            try:
                # Ensure instance folder exists
                if not os.path.exists(app.instance_path):
                    os.makedirs(app.instance_path, exist_ok=True)

                # Save file temporarily
                temp_path = os.path.join(app.instance_path, 'temp_import.csv')
                file.save(temp_path)
                
                # Process
                global BUSY_MODE
                BUSY_MODE = True
                try:
                    success, message, imported_count, duplicates = process_csv_import(temp_path, gid)
                finally:
                    BUSY_MODE = False
                
                if success:
                    # If there are duplicates, show the review page
                    if duplicates:
                         # Generate unique ID for this import session
                         import_id = str(uuid.uuid4())
                         
                         # Save duplicates to temp file
                         session_data = {
                             'duplicates': duplicates,
                             'imported_count': imported_count,
                             'duplicate_count': len(duplicates),
                             'timestamp': datetime.now().isoformat()
                         }
                         
                         # Ensure directory exists
                         temp_dir = os.path.join(app.instance_path, 'temp_imports')
                         os.makedirs(temp_dir, exist_ok=True)
                         
                         with open(os.path.join(temp_dir, f'{import_id}.json'), 'w', encoding='utf-8') as f:
                             json.dump(session_data, f)
                             
                         # Flash about imported items
                         if imported_count > 0:
                             flash(f'Succes: {imported_count} tranzacții au fost importate automat.', 'success')
                             
                         return render_template('import_review.html', 
                                              duplicates=duplicates,
                                              import_id=import_id)
                    else:
                         flash(f'Succes: {imported_count} tranzacții importate. Nu s-au găsit duplicate.', 'success')
                else:
                    flash(f'Eroare la import: {message}', 'danger')

            except Exception as e:
                import traceback
                traceback.print_exc()
                flash(f'Eroare internă server: {str(e)}', 'danger')
            
            
            
            return redirect(url_for('upload_file'))

    # GET: Show unallocated transactions for this gestiune
    gid = session.get('gestiune_id')
    unallocated = Transaction.query.filter_by(company_id=None, gestiune_id=gid).all()
    companies = Company.query.filter_by(gestiune_id=gid).order_by(Company.name).all()
    
    return render_template('import.html', unallocated=unallocated, companies=companies)

@app.route('/import-decision', methods=['POST'])
def import_decision():
    import_id = request.form.get('import_id')
    
    temp_dir = os.path.join(app.instance_path, 'temp_imports')
    temp_file = os.path.join(temp_dir, f'{import_id}.json')
    
    imported_count = 0
    duplicate_count = 0
    
    try:
        if os.path.exists(temp_file):
            with open(temp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                imported_count = data.get('imported_count', 0)
                duplicate_count = data.get('duplicate_count', 0)
            os.remove(temp_file)
    except:
        pass
        
    flash(f'Import finalizat. {imported_count} rânduri preluate, {duplicate_count} duplicate ignorate.', 'success')
        
    return redirect(url_for('dashboard'))

@app.route('/api/transaction/<int:id>')
def get_transaction_api(id):
    from models import Transaction
    gid = session.get('gestiune_id')
    t = Transaction.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    
    return jsonify({
        'id': t.id,
        'date': t.date.strftime('%d.%m.%Y'),
        'time': t.date.strftime('%H:%M'),
        'plate': t.vehicle.plate_number if t.vehicle else 'N/A',
        'quantity': t.quantity,
        'company': t.company.name if t.company else 'Nealocat',
        'company_color': t.company.color_hex if t.company else '#6c757d'
    })

@app.route('/admin/database/export')
def export_database():
    """Export ONLY the active profile's data into a standalone SQLite file."""
    import sqlite3
    import tempfile
    import unicodedata
    
    gid = session.get('gestiune_id')
    if not gid:
        flash('Nu există nici o gestiune activă selectată!', 'danger')
        return redirect('/select-profile')
    
    try:
        from models import Gestiune
        gestiune = Gestiune.query.get(gid)
        if not gestiune:
            flash('Gestiunea activă nu a fost găsită!', 'danger')
            return redirect('/data-management')
        
        # Get actual DB path from config
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri.replace('sqlite:///', '')
        else:
            # Fallback
            db_path = 'fuel_manager.db'

        if not os.path.exists(db_path):
            flash(f'Baza de date nu a fost găsită! ({db_path})', 'danger')
            return redirect('/data-management')
        
        # Create a clean profile name for the filename (remove diacritics, spaces)
        def clean_filename(name):
            # Remove diacritics
            nfkd = unicodedata.normalize('NFKD', name)
            ascii_name = nfkd.encode('ASCII', 'ignore').decode('ASCII')
            # Replace spaces and special chars with underscore
            return ''.join(c if c.isalnum() else '_' for c in ascii_name).strip('_')
        
        profile_name = clean_filename(gestiune.name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        export_filename = f'FuelManager_{profile_name}_{timestamp}.db'
        
        # Create temp export file
        temp_dir = tempfile.gettempdir()
        export_path = os.path.join(temp_dir, export_filename)
        
        # Connect to source database
        src_conn = sqlite3.connect(str(db_path))
        src_cursor = src_conn.cursor()
        
        # Create export database with clean schema
        dst_conn = sqlite3.connect(export_path)
        dst_cursor = dst_conn.cursor()
        
        # --- Create tables in export DB (mirroring current schema) ---
        dst_cursor.executescript('''
            CREATE TABLE IF NOT EXISTS gestiune (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                site_code VARCHAR(20),
                default_fuel_type VARCHAR(20) DEFAULT 'Motorină',
                logo_path VARCHAR(200),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS vehicle_category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) NOT NULL,
                description VARCHAR(200),
                icon VARCHAR(50) DEFAULT 'bi-tag-fill',
                gestiune_id INTEGER REFERENCES gestiune(id)
            );
            CREATE TABLE IF NOT EXISTS company (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                cui VARCHAR(20),
                address VARCHAR(200),
                product_code VARCHAR(50),
                gestiune_id INTEGER REFERENCES gestiune(id),
                last_report_start TIMESTAMP,
                last_report_end TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS vehicle (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number VARCHAR(50) NOT NULL,
                company_id INTEGER,
                category_id INTEGER,
                gestiune_id INTEGER REFERENCES gestiune(id)
            );
            CREATE TABLE IF NOT EXISTS stock_operation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type VARCHAR(20),
                quantity FLOAT NOT NULL,
                date DATETIME,
                description VARCHAR(200),
                company_id INTEGER,
                gestiune_id INTEGER REFERENCES gestiune(id)
            );
            CREATE TABLE IF NOT EXISTS [transaction] (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATETIME NOT NULL,
                vehicle_id INTEGER,
                company_id INTEGER,
                quantity FLOAT NOT NULL,
                gestiune_id INTEGER REFERENCES gestiune(id)
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key VARCHAR(50) NOT NULL,
                value VARCHAR(200),
                gestiune_id INTEGER REFERENCES gestiune(id)
            );
        ''')
        
        # --- Export data filtered by gestiune_id ---
        
        # 0. Export current Gestiune profile
        from models import Gestiune
        current_gest = Gestiune.query.get(gid)
        if current_gest:
            dst_cursor.execute(
                'INSERT INTO gestiune (id, name, site_code, default_fuel_type, logo_path, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                (current_gest.id, current_gest.name, current_gest.site_code, current_gest.default_fuel_type, current_gest.logo_path, current_gest.created_at)
            )
        
        # 1. Categories
        src_cursor.execute(
            'SELECT id, name, description, icon, gestiune_id FROM vehicle_category WHERE gestiune_id = ?', (gid,))
        categories = src_cursor.fetchall()
        cat_id_map = {}  # old_id -> new_id (to remap foreign keys)
        for row in categories:
            dst_cursor.execute(
                'INSERT INTO vehicle_category (name, description, icon, gestiune_id) VALUES (?, ?, ?, ?)',
                (row[1], row[2], row[3], row[4]))
            cat_id_map[row[0]] = dst_cursor.lastrowid
        
        # 2. Companies
        src_cursor.execute(
            'SELECT id, name, cui, address, product_code, gestiune_id FROM company WHERE gestiune_id = ?', (gid,))
        companies = src_cursor.fetchall()
        comp_id_map = {}
        for row in companies:
            dst_cursor.execute(
                'INSERT INTO company (name, cui, address, product_code, gestiune_id) VALUES (?, ?, ?, ?, ?)',
                (row[1], row[2], row[3], row[4], row[5]))
            comp_id_map[row[0]] = dst_cursor.lastrowid
        
        # 3. Vehicles (remap company_id and category_id)
        src_cursor.execute(
            'SELECT id, plate_number, company_id, category_id, gestiune_id FROM vehicle WHERE gestiune_id = ?', (gid,))
        vehicles = src_cursor.fetchall()
        veh_id_map = {}
        for row in vehicles:
            new_comp_id = comp_id_map.get(row[2])
            new_cat_id = cat_id_map.get(row[3])
            dst_cursor.execute(
                'INSERT INTO vehicle (plate_number, company_id, category_id, gestiune_id) VALUES (?, ?, ?, ?)',
                (row[1], new_comp_id, new_cat_id, row[4]))
            veh_id_map[row[0]] = dst_cursor.lastrowid
        
        # 4. Stock Operations (remap company_id)
        src_cursor.execute(
            'SELECT id, operation_type, quantity, date, description, company_id, gestiune_id '
            'FROM stock_operation WHERE gestiune_id = ?', (gid,))
        stock_ops = src_cursor.fetchall()
        for row in stock_ops:
            new_comp_id = comp_id_map.get(row[5])
            dst_cursor.execute(
                'INSERT INTO stock_operation (operation_type, quantity, date, description, company_id, gestiune_id) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (row[1], row[2], row[3], row[4], new_comp_id, row[6]))
        
        # 5. Transactions (remap vehicle_id and company_id)
        src_cursor.execute(
            'SELECT id, date, vehicle_id, company_id, quantity, gestiune_id '
            'FROM [transaction] WHERE gestiune_id = ?', (gid,))
        transactions = src_cursor.fetchall()
        for row in transactions:
            new_veh_id = veh_id_map.get(row[2])
            new_comp_id = comp_id_map.get(row[3])
            if new_veh_id:  # Skip orphaned transactions
                dst_cursor.execute(
                    'INSERT INTO [transaction] (date, vehicle_id, company_id, quantity, gestiune_id) '
                    'VALUES (?, ?, ?, ?, ?)',
                    (row[1], new_veh_id, new_comp_id, row[4], row[5]))
        
        # 6. App Settings (tank capacity, etc.)
        try:
            src_cursor.execute(
                'SELECT key, value, gestiune_id FROM app_settings WHERE gestiune_id = ?', (gid,))
            settings = src_cursor.fetchall()
            for row in settings:
                dst_cursor.execute(
                    'INSERT INTO app_settings (key, value, gestiune_id) VALUES (?, ?, ?)',
                    (row[0], row[1], row[2]))
        except Exception:
            pass  # Table might not exist in older DBs
        
        dst_conn.commit()
        dst_conn.close()
        src_conn.close()
        
        print(f"[EXPORT] Profile '{gestiune.name}' (id={gid}): "
              f"{len(categories)} cat, {len(companies)} comp, {len(vehicles)} veh, "
              f"{len(stock_ops)} stock, {len(transactions)} trans")
        
        # PDF System v6.1 style: Save copy to Downloads if in Desktop Mode
        if os.environ.get('DESKTOP_MODE') == '1':
            try:
                downloads_path = Path.home() / "Downloads"
                final_dest = downloads_path / export_filename
                shutil.copy2(export_path, str(final_dest))
                print(f"[EXPORT] Saved copy to Downloads: {final_dest}")
            except Exception as e:
                print(f"[EXPORT] Failed to save copy to Downloads: {e}")

        return send_file(
            export_path,
            as_attachment=True,
            download_name=export_filename
        )
    except Exception as e:
        flash(f'Eroare la export: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect('/data-management')

@app.route('/admin/stock/details')
def stock_details():
    from models import Company, StockOperation, Transaction, Vehicle
    from datetime import datetime
    from sqlalchemy import func
    
    gid = session.get('gestiune_id')
    companies = Company.query.filter_by(gestiune_id=gid).all()
    stocks_data = {}
    for c in companies:
        # Get operations
        ops = StockOperation.query.filter_by(company_id=c.id, gestiune_id=gid).all()
        # Only include fully allocated transactions (have vehicle AND category)
        from models import Vehicle
        trans = Transaction.query.join(Vehicle, Transaction.vehicle_id == Vehicle.id)\
            .filter(Transaction.company_id == c.id, 
                    Transaction.gestiune_id == gid,
                    Vehicle.category_id != None).all()
        
        history = []
        for o in ops:
            history.append({
                'id': o.id,
                'date': o.date,
                'type': o.operation_type,
                'quantity': o.quantity,
                'description': o.description or '',
                'category': ''
            })
        for t in trans:
            history.append({
                'id': t.id,
                'date': t.date,
                'type': 'TRANSACTION',
                'quantity': t.quantity,
                'description': t.vehicle.plate_number if t.vehicle else 'Unknown',
                'category': t.vehicle.category.name if (t.vehicle and t.vehicle.category) else '',
                'is_unallocated': (t.vehicle is None) or (t.vehicle.company_id is None) or (t.vehicle.category_id is None)
            })
            
        # Sort by date descending (newest first)
        history.sort(key=lambda x: x['date'], reverse=True)
        
        # Calc stats
        initial = sum(x['quantity'] for x in history if x['type'] == 'INITIAL')
        refill = sum(x['quantity'] for x in history if x['type'] == 'IN')
        consumed = sum(x['quantity'] for x in history if x['type'] in ['TRANSACTION', 'OUT'])
        current = initial + refill - consumed
        
        stocks_data[c.id] = {
            'initial': initial,
            'in': refill,
            'consumed': consumed,
            'current': current,
            'history': history,
            'last_update': (lambda t, o: max([d for d in [t, o] if d]) if (t or o) else None)(
                db.session.query(func.max(Transaction.date)).filter_by(company_id=c.id, gestiune_id=gid).scalar(),
                db.session.query(func.max(StockOperation.date)).filter_by(company_id=c.id, gestiune_id=gid).scalar()
            ),
            'color': c.color,
            'color_hex': c.color_hex
        }

    # NEW: Handle unallocated transactions separately 
    # 1. Unallocated Transactions (No company OR No vehicle OR No category)
    from models import Vehicle
    unallocated_trans = Transaction.query.outerjoin(Vehicle, Transaction.vehicle_id == Vehicle.id)\
        .filter(Transaction.gestiune_id == gid,
                db.or_(Transaction.company_id == None, Transaction.vehicle_id == None, Vehicle.category_id == None)).all()
    
    # 2. Unallocated Stock Operations (Ghosts)
    unallocated_ops = StockOperation.query.filter_by(company_id=None, gestiune_id=gid).all()
    
    unallocated_history = []
    
    for t in unallocated_trans:
        # Check for potential duplicates (same date, same quantity, different ID)
        duplicate_check = Transaction.query.filter_by(
            date=t.date, 
            quantity=t.quantity, 
            gestiune_id=gid
        ).filter(Transaction.id != t.id).first()
        
        duplicate_info = None
        if duplicate_check:
            plate = duplicate_check.vehicle.plate_number if duplicate_check.vehicle else "N/A"
            duplicate_info = {
                'plate': plate,
                'id': duplicate_check.id
            }

        unallocated_history.append({
            'id': t.id,
            'date': t.date,
            'type': 'TRANSACTION',
            'item_type': 'trans',
            'quantity': t.quantity,
            'description': t.vehicle.plate_number if t.vehicle else 'Unknown',
            'category': t.vehicle.category.name if (t.vehicle and t.vehicle.category) else '',
            'is_unallocated': True,
            'duplicate_info': duplicate_info
        })

    for op in unallocated_ops:
        desc = "Operatiune Stoc"
        if op.operation_type == 'IN': desc = "Intrare Stoc (Refill)"
        elif op.operation_type == 'INITIAL': desc = "Stoc Initial"
        elif op.operation_type == 'OUT': desc = "Iesire Manuala"
        
        unallocated_history.append({
            'id': op.id,
            'date': op.date,
            'type': op.operation_type,
            'item_type': 'op',
            'quantity': op.quantity,
            'description': op.description or desc,
            'category': 'SISTEM',
            'is_unallocated': True
        })
        
    unallocated_history.sort(key=lambda x: x['date'], reverse=True)
    # Only sum transactions for 'consumed' metric
    # Sum ALL unallocated items (Transactions + Ops) to match Dashboard
    
    # Calculate breakdown
    unallocated_initial = sum(x['quantity'] for x in unallocated_history if x.get('type') == 'INITIAL')
    unallocated_in = sum(x['quantity'] for x in unallocated_history if x.get('type') == 'IN')
    unallocated_out = sum(x['quantity'] for x in unallocated_history if x.get('type') == 'OUT')
    unallocated_trans_qty = sum(x['quantity'] for x in unallocated_history if x.get('item_type') == 'trans')
    
    # "Consumed" in summary usually means Transactions + Manual Out
    unallocated_consumed_total = unallocated_trans_qty + unallocated_out
    
    # "Current Stock" for unallocated is basically the net sum: (Initial + In) - (Trans + Out)
    # But usually unallocated items are just "there". 
    # If we treat them as a "Company" holding this stock:
    unallocated_current = unallocated_initial + unallocated_in - unallocated_consumed_total
    
    # For the dashboard card, we typically show the "Net Positive" presence or just the sum of everything?
    # The dashboard card shows "Unallocated Consumed" which was just a sum.
    # The user complained "28000 liter" which is the POSITIVE stock (Initial+In).
    # So "Stoc Actual" should be the net value.
    
    # We pass these to template
    
    # Get all vehicles for autocomplete for this gestiune
    all_vehicles = Vehicle.query.filter_by(gestiune_id=gid).all()
    vehicles_data = [v.plate_number for v in all_vehicles]

    return render_template('stock_details.html', 
                         companies=companies, 
                         stocks=stocks_data, 
                         now=datetime.now().strftime('%Y-%m-%dT%H:%M'), 
                         active_company_id=request.args.get('company_id', type=int),
                         vehicles_autocomplete=vehicles_data,
                         unallocated_history=unallocated_history,
                         unallocated_stats={
                             'initial': unallocated_initial,
                             'in': unallocated_in,
                             'consumed': unallocated_consumed_total,
                             'current': unallocated_current
                         })

@app.route('/admin/stock/add_detailed', methods=['POST'])
def add_stock_detailed():
    from models import StockOperation
    from datetime import datetime
    from services import HistoryService
    
    gid = session.get('gestiune_id')
    company_id = int(request.form['company_id'])
    op_type = request.form['operation_type']
    qty = float(request.form['quantity'])
    desc = request.form['description']
    date_str = request.form['date']
    date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    
    if op_type == 'OUT' and desc.strip():
        from models import Vehicle, Transaction, VehicleCategory
        plate = desc.strip().upper().replace(' ', '').replace('-', '') # Normalize for search
        # Find or create vehicle
        vehicle = Vehicle.query.filter_by(plate_number=plate, gestiune_id=gid).first()
        if not vehicle:
            # Get default category
            cat = VehicleCategory.query.filter_by(name='Autoturism', gestiune_id=gid).first()
            if not cat:
                # Fallback
                cat = VehicleCategory.query.filter_by(gestiune_id=gid).first()
            
            vehicle = Vehicle(plate_number=plate, company_id=company_id, category_id=cat.id if cat else None, gestiune_id=gid)
            db.session.add(vehicle)
            db.session.flush()
            flash(f"Vehicul nou înregistrat: {plate}", "info")
        
        # Create as Transaction for analysis
        op = Transaction(quantity=qty, vehicle_id=vehicle.id, company_id=company_id, date=date, gestiune_id=gid)
        db.session.add(op)
        db.session.commit()
        HistoryService.log_action('Transaction', op.id, 'CREATE', op, gestiune_id=gid)
    else:
        op = StockOperation(quantity=qty, operation_type=op_type, description=desc, date=date, company_id=company_id, gestiune_id=gid)
        db.session.add(op)
        db.session.commit()
        HistoryService.log_action('StockOperation', op.id, 'CREATE', op, gestiune_id=gid)
    
    return redirect(f'/admin/stock/details?company_id={company_id}')

@app.route('/admin/stock/edit/<int:id>', methods=['GET', 'POST'])
def edit_stock(id):
    from models import StockOperation
    from datetime import datetime
    from services import HistoryService
    
    gid = session.get('gestiune_id')
    op = StockOperation.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    
    if request.method == 'POST':
        # LOG PRE-UPDATE
        HistoryService.log_action('StockOperation', op.id, 'UPDATE', op, gestiune_id=gid)
        
        op.operation_type = request.form['operation_type']
        op.quantity = float(request.form['quantity'])
        op.description = request.form['description']
        date_str = request.form['date']
        op.date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        
        db.session.commit()
        return redirect(f'/admin/stock/details?company_id={op.company_id}')
        
    return render_template('edit_stock.html', operation=op)

@app.route('/admin/transaction/edit/<int:id>', methods=['GET', 'POST'])
def edit_transaction(id):
    from models import Transaction, Vehicle, Company
    from datetime import datetime
    from services import HistoryService
    
    gid = session.get('gestiune_id')
    t = Transaction.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    
    if request.method == 'POST':
        # LOG PRE-UPDATE
        HistoryService.log_action('Transaction', t.id, 'UPDATE', t, gestiune_id=gid)
        
        new_quantity = float(request.form['quantity'])
        date_str = request.form['date']
        new_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        
        # Handle vehicle change (Manual input or selection)
        plate_input = request.form.get('plate_input', '').strip().upper()
        new_vehicle_id = t.vehicle_id
        new_company_id = t.company_id
        
        if plate_input:
            # Check if exists in this gestiune
            v = Vehicle.query.filter_by(plate_number=plate_input, gestiune_id=gid).first()
            
            if not v:
                # Create new vehicle (Unallocated) in this gestiune
                v = Vehicle(plate_number=plate_input, company_id=None, gestiune_id=gid) 
                db.session.add(v)
                db.session.flush() # Get ID
                flash(f"Vehicul nou creat: {plate_input}", "info")
            
            new_vehicle_id = v.id
            # Only update company if the NEW vehicle has one assigned
            if v.company_id:
                new_company_id = v.company_id
        
        try:
            # Update values
            t.quantity = new_quantity
            t.date = new_date
            t.vehicle_id = new_vehicle_id
            t.company_id = new_company_id
            
            db.session.commit()
            
            target_cid = t.company_id if t.company_id else -1
            flash("Alimentare actualizată.", "success")
            return redirect(url_for('stock_details', company_id=target_cid))
            
        except Exception as e:
            db.session.rollback()
            # Check if it's an IntegrityError (duplicate)
            if "UNIQUE constraint failed" in str(e):
                flash("Eroare: Această tranzacție există deja pentru vehiculul/data selectată. Nu s-au făcut modificări.", "danger")
            else:
                flash(f"Eroare la salvare: {str(e)}", "danger")
            return redirect(url_for('edit_transaction', id=id))
        
    # Get all vehicles for dropdown for this gestiune
    vehicles = Vehicle.query.filter_by(gestiune_id=gid).order_by(Vehicle.plate_number).all()
    return render_template('edit_transaction.html', transaction=t, vehicles=vehicles)

@app.route('/admin/stock/delete/<int:id>')
def delete_stock(id):
    from models import StockOperation
    from services import HistoryService
    
    gid = session.get('gestiune_id')
    op = StockOperation.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    company_id = op.company_id
    
    # LOG
    HistoryService.log_action('StockOperation', op.id, 'DELETE', op, gestiune_id=gid)
    
    db.session.delete(op)
    db.session.commit()
    flash("Operațiunea a fost ștearsă.", "success")
    return redirect(f'/admin/stock/details?company_id={company_id}')

@app.route('/admin/transaction/delete/<int:id>')
def delete_transaction(id):
    from models import Transaction
    
    gid = session.get('gestiune_id')
    trans = Transaction.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    redirect_url = request.args.get('redirect', '/admin/stock/details')
    
    db.session.delete(trans)
    db.session.commit()
    
    flash("Tranzacția sursă a fost ștearsă.", "success")
    return redirect(redirect_url)

@app.route('/admin/transaction/accept/<int:id>/<int:company_id>')
def accept_transaction(id, company_id):
    from models import Transaction
    
    gid = session.get('gestiune_id')
    trans = Transaction.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    trans.company_id = company_id
    db.session.commit()
    
    redirect_url = request.args.get('redirect', '/upload')
    flash("Tranzacția a fost acceptată și alocată cu succes.", "success")
    return redirect(redirect_url)

@app.route('/admin/stock/move/<string:type>/<int:id>', methods=['GET', 'POST'])
def move_stock(type, id):
    from models import StockOperation, Transaction, Company, VehicleCategory
    
    gid = session.get('gestiune_id')
    categories = VehicleCategory.query.filter_by(gestiune_id=gid).all()
    
    # Identify the object
    if type == 'op':
        item = StockOperation.query.filter_by(id=id, gestiune_id=gid).first_or_404()
        desc = item.description or f"{item.operation_type} Operation"
        qty = item.quantity
        curr_comp = item.company.name if item.company else 'Unknown'
        curr_cat = None
    elif type == 'trans':
        item = Transaction.query.filter_by(id=id, gestiune_id=gid).with_for_update().first_or_404()
        desc = f"Alimentare {item.vehicle.plate_number if item.vehicle else 'Unknown'}"
        qty = item.quantity
        curr_comp = item.company.name if item.company else 'Unknown'
        curr_cat = item.vehicle.category.name if (item.vehicle and item.vehicle.category) else 'Nici o categorie'
    else:
        return "Invalid type", 400
        
    if request.method == 'POST':
        new_company_id = request.form.get('new_company_id')
        new_category_id = request.form.get('new_category_id')

        if new_company_id:
            item.company_id = int(new_company_id)
            
        # Category assignment is OPTIONAL (only if provided and valid)
        if new_category_id and new_category_id.strip() and type == 'trans' and item.vehicle:
            item.vehicle.category_id = int(new_category_id)

        db.session.commit()
        return redirect(f'/admin/stock/details?company_id={item.company_id}')
        
    companies = Company.query.filter_by(gestiune_id=gid).all()
    return render_template('move_stock.html', 
                         item_desc=desc, 
                         item_qty=qty, 
                         current_company=curr_comp, 
                         current_category=curr_cat,
                         companies=companies,
                         categories=categories,
                         item_type=type)

@app.route('/admin/stock/allocate_bulk', methods=['POST'])
def allocate_bulk():
    from models import Transaction
    
    gid = session.get('gestiune_id')
    transaction_ids = request.form.getlist('transaction_ids')
    operation_ids = request.form.getlist('operation_ids')
    target_company_id = request.form.get('target_company_id')
    
    if not target_company_id or (not transaction_ids and not operation_ids):
        flash('Selectați elemente și firma țintă.', 'warning')
        return redirect('/admin/stock/details')
    
    # Bulk update
    count = 0
    # Process Transactions
    if transaction_ids:
        for tid in transaction_ids:
            trans = Transaction.query.filter_by(id=int(tid), gestiune_id=gid).first()
            if trans:
                trans.company_id = int(target_company_id)
                count += 1

    # Process Stock Operations (Ghosts)
    if operation_ids:
        from models import StockOperation
        for oid in operation_ids:
            op = StockOperation.query.filter_by(id=int(oid), gestiune_id=gid).first()
            if op:
                op.company_id = int(target_company_id)
                count += 1
    
    db.session.commit()
    flash(f'{count} elemente alocate cu succes.', 'success')
    return redirect('/admin/stock/details') # Will fallback to unallocated if items remain


@app.route('/admin/stock/delete_bulk', methods=['POST'])
def delete_stock_bulk():
    from models import StockOperation, Transaction
    from services import HistoryService
    
    # 1. Try to get items from the "Unified" list (Company Tab style: "type:id")
    items = request.form.getlist('operation_ids')
    
    # 2. Try to get items from separate lists (Unallocated Tab style)
    trans_ids_from_form = request.form.getlist('transaction_ids')
    
    op_ids_to_delete = []
    trans_ids_to_delete = []
    
    gid = session.get('gestiune_id')
    company_id = None

    # Helper to process mixed list
    for item in items:
        if ':' in item:
            # Company Tab Format: "type:id"
            try:
                type_str, id_str = item.split(':')
                itemId = int(id_str)
                if type_str == 'op':
                    op_ids_to_delete.append(itemId)
                    op = StockOperation.query.filter_by(id=itemId, gestiune_id=gid).first()
                    if op and not company_id: company_id = op.company_id
                elif type_str == 'trans':
                    trans_ids_to_delete.append(itemId)
                    t = Transaction.query.filter_by(id=itemId, gestiune_id=gid).first()
                    if t and not company_id: company_id = t.company_id
            except ValueError:
                continue
        else:
            # Unallocated Tab Format (it uses 'operation_ids' for ops only)
            try:
                itemId = int(item)
                op_ids_to_delete.append(itemId)
            except ValueError:
                continue
                
    # Add explicitly named transaction_ids (from Unallocated tab)
    for tid in trans_ids_from_form:
        try:
            trans_ids_to_delete.append(int(tid))
        except ValueError:
            continue
            
    # LOG ACTIONS BEFORE DELETE (for Undo)
    deleted_count = 0
    if op_ids_to_delete:
        ops = StockOperation.query.filter(StockOperation.id.in_(op_ids_to_delete)).all()
        for op in ops:
            HistoryService.log_action('StockOperation', op.id, 'DELETE', op, gestiune_id=gid)
            db.session.delete(op)
            deleted_count += 1
    
    if trans_ids_to_delete:
        transactions = Transaction.query.filter(Transaction.id.in_(trans_ids_to_delete)).all()
        for t in transactions:
            HistoryService.log_action('Transaction', t.id, 'DELETE', t, gestiune_id=gid)
            db.session.delete(t)
            deleted_count += 1
        
    db.session.commit()
    
    flash(f"{deleted_count} elemente au fost șterse.", "success")
    if company_id:
         return redirect(f'/admin/stock/details?company_id={company_id}')
         
    return redirect('/admin/stock/details')

@app.route('/admin/stock/rename_vehicle_bulk', methods=['POST'])
def rename_vehicle_bulk():
    from models import StockOperation, Transaction, Vehicle
    from services import HistoryService
    
    gid = session.get('gestiune_id')
    new_plate = request.form.get('new_plate', '').strip().upper()
    
    if not new_plate:
        flash('Introduceți un număr de înmatriculare valid.', 'warning')
        return redirect('/admin/stock/details')

    # Find or Create Vehicle in this gestiune
    v = Vehicle.query.filter_by(plate_number=new_plate, gestiune_id=gid).first()
    if not v:
        v = Vehicle(plate_number=new_plate, gestiune_id=gid)
        db.session.add(v)
        db.session.flush()

    # Get items
    items = request.form.getlist('operation_ids')
    trans_ids_from_form = request.form.getlist('transaction_ids')
    
    count = 0
    company_id = None
    
    # Process mixed items (Company Tab)
    for item in items:
        if ':' in item:
            type_str, id_str = item.split(':')
            itemId = int(id_str)
            if type_str == 'trans':
                t = Transaction.query.filter_by(id=itemId, gestiune_id=gid).first()
                if t:
                    HistoryService.log_action('Transaction', t.id, 'UPDATE', t, gestiune_id=gid)
                    t.vehicle_id = v.id
                    if v.company_id: t.company_id = v.company_id
                    if not company_id: company_id = t.company_id
                    count += 1
            else: # op
                op = StockOperation.query.filter_by(id=itemId, gestiune_id=gid).first()
                if op:
                    HistoryService.log_action('StockOperation', op.id, 'UPDATE', op, gestiune_id=gid)
                    op.description = f"Redenumit: {new_plate} (original: {op.description})"
                    if not company_id: company_id = op.company_id
                    count += 1
        else: # ID only (Unallocated Tab Ops)
            op = StockOperation.query.filter_by(id=int(item), gestiune_id=gid).first()
            if op:
                HistoryService.log_action('StockOperation', op.id, 'UPDATE', op, gestiune_id=gid)
                op.description = f"Redenumit: {new_plate}"
                count += 1

    # Process explicit transaction IDs (Unallocated Tab)
    for tid in trans_ids_from_form:
        t = Transaction.query.filter_by(id=int(tid), gestiune_id=gid).first()
        if t:
            HistoryService.log_action('Transaction', t.id, 'UPDATE', t, gestiune_id=gid)
            t.vehicle_id = v.id
            if v.company_id: t.company_id = v.company_id
            count += 1

    db.session.commit()
    flash(f'{count} elemente au fost redenumite la {new_plate}.', 'success')
    
    if company_id:
        return redirect(f'/admin/stock/details?company_id={company_id}')
    return redirect('/admin/stock/details')

@app.route('/admin/stock/move_bulk', methods=['POST'])
def move_stock_bulk():
    from models import StockOperation, Transaction
    
    items = request.form.getlist('operation_ids')
    trans_ids = request.form.getlist('transaction_ids')
    
    new_company_id = request.form.get('new_company_id') or request.form.get('new_company_id_bottom')
    
    if not new_company_id:
        return redirect('/admin/stock/details')
        
    new_company_id = int(new_company_id)
    gid = session.get('gestiune_id')
    
    # Process mixed format items and plain operation IDs
    for item in items:
        try:
            if ':' in item:
                type_str, id_str = item.split(':')
                itemId = int(id_str)
                
                if type_str == 'op':
                    op = StockOperation.query.filter_by(id=itemId, gestiune_id=gid).first()
                    if op: op.company_id = new_company_id
                elif type_str == 'trans':
                    trans = Transaction.query.filter_by(id=itemId, gestiune_id=gid).first()
                    if trans: trans.company_id = new_company_id
            else:
                # Assume Op ID if no prefix (Unallocated Tab format for Ops)
                itemId = int(item)
                op = StockOperation.query.filter_by(id=itemId, gestiune_id=gid).first()
                if op: op.company_id = new_company_id
                
        except ValueError:
            continue
            
    # Process explicit Transaction IDs (Unallocated Tab format for Trans)
    for tid in trans_ids:
        try:
            itemId = int(tid)
            trans = Transaction.query.filter_by(id=itemId, gestiune_id=gid).first()
            if trans: trans.company_id = new_company_id
        except ValueError:
            continue
            
    db.session.commit()
    flash(f'Am mutat {len(items) + len(trans_ids)} elemente.', 'success')
    return redirect('/admin/stock/details') # Back to origin (usually unallocated)

@app.route('/admin/stock/delete_item/<string:type>/<int:id>')
def delete_item(type, id):
    from models import StockOperation, Transaction
    from services import HistoryService
    
    gid = session.get('gestiune_id')
    company_id = None
    
    if type == 'op':
        op = StockOperation.query.filter_by(id=id, gestiune_id=gid).first_or_404()
        company_id = op.company_id
        # LOG
        HistoryService.log_action('StockOperation', op.id, 'DELETE', op, gestiune_id=gid)
        db.session.delete(op)
    elif type == 'trans':
        t = Transaction.query.filter_by(id=id, gestiune_id=gid).first_or_404()
        company_id = t.company_id
        HistoryService.log_action('Transaction', t.id, 'DELETE', t, gestiune_id=gid)
        db.session.delete(t)
    db.session.commit()
    
    if company_id:
        return redirect(f'/admin/stock/details?company_id={company_id}')
    return redirect('/admin/stock/details')

@app.route('/admin/history/undo')
def history_undo():
    from services import HistoryService
    gid = session.get('gestiune_id')
    company_id = request.args.get('company_id')
    
    success, message = HistoryService.undo(gid)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'warning')
        
    return redirect(url_for('stock_details', company_id=company_id) if company_id else '/admin/stock/details')

@app.route('/admin/history/redo')
def history_redo():
    from services import HistoryService
    gid = session.get('gestiune_id')
    company_id = request.args.get('company_id')
    
    success, message = HistoryService.redo(gid)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'warning')
        
    return redirect(url_for('stock_details', company_id=company_id) if company_id else '/admin/stock/details')




@app.route('/reports', methods=['GET'])
def reports_page():
    from models import Company
    from datetime import datetime
    
    gid = session.get('gestiune_id')
    companies = Company.query.filter_by(gestiune_id=gid).order_by(Company.name).all()
    
    now = datetime.now()
    default_start = now.replace(hour=0, minute=0).strftime('%Y-%m-%dT%H:%M')
    default_end = now.replace(hour=23, minute=59).strftime('%Y-%m-%dT%H:%M')
    
    return render_template('reports.html', companies=companies, default_start=default_start, default_end=default_end)


@app.route('/api/report_stats', methods=['GET'])
def api_report_stats():
    """
    API to get:
    1. Total consumption for a selected range (and optional company)
    2. Last saved report interval for a specific company
    """
    from models import Transaction, Company
    from sqlalchemy import func
    from datetime import datetime

    gid = session.get('gestiune_id')
    if not gid:
        return jsonify({'error': 'No active session'}), 401

    company_id = request.args.get('company_id')
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    response = {
        'total_liters': 0,
        'company_last_start': None,
        'company_last_end': None,
        'has_saved_dates': False
    }

    # 1. Fetch saved dates if company selected
    if company_id:
        try:
            cid = int(company_id)
            comp = Company.query.filter_by(id=cid, gestiune_id=gid).first()
            if comp:
                if comp.last_report_start:
                    response['company_last_start'] = comp.last_report_start.strftime('%Y-%m-%dT%H:%M')
                    response['has_saved_dates'] = True
                if comp.last_report_end:
                    response['company_last_end'] = comp.last_report_end.strftime('%Y-%m-%dT%H:%M')
        except ValueError:
            pass

    # 2. Calculate Total Liters (if dates provided)
    if start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%dT%H:%M')
            end_date = datetime.strptime(end_str, '%Y-%m-%dT%H:%M')
            
            query = db.session.query(func.sum(Transaction.quantity)).filter(
                Transaction.gestiune_id == gid,
                Transaction.date >= start_date,
                Transaction.date <= end_date
            )
            
            if company_id:
                try:
                    cid = int(company_id)
                    query = query.filter(Transaction.company_id == cid)
                except ValueError:
                    pass # Ignore invalid company_id
            
            total = query.scalar() or 0
            response['total_liters'] = total
        except ValueError:
            pass # Invalid date format

    return jsonify(response)


@app.route('/analysis', methods=['GET', 'POST'])
def analysis_page():
    from models import VehicleCategory, Transaction, Vehicle, AppSettings
    from sqlalchemy import func
    from datetime import datetime
    
    gid = session.get('gestiune_id')
    if not gid:
        return redirect('/select-profile')
        
    # Get last used dates from settings or default to current month
    saved_start = AppSettings.query.filter_by(key='analysis_last_start', gestiune_id=gid).first()
    saved_end = AppSettings.query.filter_by(key='analysis_last_end', gestiune_id=gid).first()
    
    default_start = saved_start.value if saved_start else datetime.now().replace(day=1, hour=0, minute=0).strftime('%Y-%m-%dT%H:%M')
    default_end = saved_end.value if saved_end else datetime.now().replace(hour=23, minute=59).strftime('%Y-%m-%dT%H:%M')

    # Date filters (URL takes priority, defaults to last used)
    start_date_str = request.args.get('start', default_start)
    end_date_str = request.args.get('end', default_end)
    
    # Save these as last used
    for key, val in [('analysis_last_start', start_date_str), ('analysis_last_end', end_date_str)]:
        setting = AppSettings.query.filter_by(key=key, gestiune_id=gid).first()
        if not setting:
            setting = AppSettings(key=key, value=val, gestiune_id=gid)
            db.session.add(setting)
        else:
            setting.value = val
    db.session.commit()
    
    # Persistent Calculation Basis (General)
    basis_setting = AppSettings.query.filter_by(key='analysis_calculation_basis', gestiune_id=gid).first()
    calc_basis = basis_setting.value if basis_setting else 'diferenta_mc'
    
    # Category-specific Basis Settings
    cat_basis_settings = AppSettings.query.filter(AppSettings.key.like('analysis_basis_cat_%'), AppSettings.gestiune_id == gid).all()
    cat_basis_map = {s.key.replace('analysis_basis_cat_', ''): s.value for s in cat_basis_settings}
    
    # Visibility and filtering settings
    visible_setting = AppSettings.query.filter_by(key='analysis_visible_categories', gestiune_id=gid).first()
    visible_categories = json.loads(visible_setting.value) if visible_setting else []
    
    hidden_setting = AppSettings.query.filter_by(key='analysis_exclude_hidden', gestiune_id=gid).first()
    exclude_hidden = hidden_setting.value == 'true' if hidden_setting else False
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
    
    # MC Keys updated for v5.6 (Removed mc_pe_statie)
    mc_keys = [
        'total_mc_vanduti', 'mc_balast', 'mc_exploatati', 
        'to_cap_tractor', 'mc_balast_sortati', 'consum_extra_8x4',
        'nisip_exploatat_ghidfalau', 'nisip_transportat_budila', 'consum_extra_ghidfalau'
    ]
    
    if request.method == 'POST':
        for key in mc_keys:
            val = request.form.get(key, '0')
            # Save using AppSettings helper or manual update
            setting = AppSettings.query.filter_by(key=f'analysis_{key}', gestiune_id=gid).first()
            if not setting:
                setting = AppSettings(key=f'analysis_{key}', value=str(val), gestiune_id=gid)
                db.session.add(setting)
            else:
                setting.value = str(val)
        db.session.commit()
        flash("Valorile de producție au fost actualizate.", "success")
        return redirect(url_for('analysis_page', start=start_date_str, end=end_date_str))
        
    # Get current MC values
    mc_values = {}
    for key in mc_keys:
        setting = AppSettings.query.filter_by(key=f'analysis_{key}', gestiune_id=gid).first()
        try:
            val = float(setting.value) if setting and setting.value else 0.0
        except:
            val = 0.0
        mc_values[key] = val
        
    # CALCULATED FIELDS (v5.5 Logic)
    # c. Sorturi Vanduti = Total Vanduti - Balast Vanduti
    mc_values['mc_sorturi_vanduti'] = mc_values['total_mc_vanduti'] - mc_values['mc_balast']
    
    # f. Stoc Statie = Exploatati - Sortati
    mc_values['mc_stoc_statie'] = mc_values['mc_exploatati'] - mc_values['mc_balast_sortati']
    
    # g. Cap Tractor Conversion (Tone -> MC / 1.5)
    if mc_values['to_cap_tractor'] > 0:
        mc_values['mc_cap_tractor'] = mc_values['to_cap_tractor'] / 1.5
    else:
        mc_values['mc_cap_tractor'] = 0.0
        
    # h. Consum Extra (for efficiency calculation)
    consum_extra = mc_values.get('consum_extra_8x4', 0.0)
    
    # Aggregation logic: Fuel consumption per Category
    # Join Transaction -> Vehicle -> VehicleCategory
    stats = db.session.query(
        VehicleCategory.name,
        func.sum(Transaction.quantity).label('total_fuel'),
        func.max(VehicleCategory.id).label('cat_id')
    ).join(Vehicle, Transaction.vehicle_id == Vehicle.id)\
     .join(VehicleCategory, Vehicle.category_id == VehicleCategory.id)\
     .filter(Transaction.gestiune_id == gid, Transaction.date >= start_date, Transaction.date <= end_date)\
     .group_by(VehicleCategory.name).all()
     
    # Define Section Categories
    budila_categories = ['VOLA', 'EXCAVATOR', 'BULDOZER', 'BOBCAT', 'CAMION 8X4', 'CAP TRACTOR', 'AUTOTURISM']
    ghidfalau_categories = ['VOLA GHIDFALĂU', 'EXCAVATOR GHIDFALĂU']
    
    # Combined fuel for Ghidfalau Index calculation
    ghidfalau_total_fuel = 0
    
    budila_data = []
    ghidfalau_data = []
    
    # All relevant categories for searching
    relevant_categories = budila_categories + ghidfalau_categories
    
    all_categories = VehicleCategory.query.filter_by(gestiune_id=gid).all()
    consumption_map = {name: {'fuel': fuel, 'id': cat_id} for name, fuel, cat_id in stats}
    
    for cat_obj in all_categories:
        # Visibility filter
        if visible_categories and cat_obj.name not in visible_categories:
            continue
            
        fuel = consumption_map.get(cat_obj.name, {}).get('fuel', 0)
        cat_id = cat_obj.id
        name_upper = cat_obj.name.upper()
        is_ghidfalau = any(kw in name_upper for kw in ['GHIDFALAU', 'GHIDFALĂU', 'GHID'])
        
        # Site-specific default basis if none saved
        default_basis = 'nisip_exploatat_ghidfalau' if is_ghidfalau else 'total_mc_vanduti'
        basis = cat_basis_map.get(cat_obj.name, default_basis)
        
        record = {
            'category': cat_obj.name,
            'category_id': cat_id,
            'fuel': fuel,
            'basis': basis,
            'icon': cat_obj.icon
        }
        
        # Determine which section it belongs to
        name_upper = cat_obj.name.upper()
        is_ghidfalau = any(kw in name_upper for kw in ['GHIDFALAU', 'GHIDFALĂU', 'GHID'])
        
        if is_ghidfalau:
            ghidfalau_data.append(record)
            ghidfalau_total_fuel += fuel
        else:
            budila_data.append(record)

    # Calculate Totals
    # We need to separate Budila and Ghidfalau fuel for accurate indexing
    # total_engine_fuel will now represent only Budila fuel
    if exclude_hidden and visible_categories:
        total_engine_fuel = sum(fuel for name, fuel, cat_id in stats 
                              if name in visible_categories and not any(kw in name.upper() for kw in ['GHID', 'GHIDFALAU', 'GHIDFALĂU']))
    else:
        total_engine_fuel = sum(fuel for name, fuel, cat_id in stats 
                              if not any(kw in name.upper() for kw in ['GHID', 'GHIDFALAU', 'GHIDFALĂU']))
    
    # Net Fuel Calculation for Budila Global Efficiency (excluding extra sales/consum)
    net_engine_fuel = total_engine_fuel
    if consum_extra > 0:
        net_engine_fuel = max(0, total_engine_fuel - consum_extra)

    ghidfalau_net_fuel = ghidfalau_total_fuel
    if mc_values.get('consum_extra_ghidfalau', 0) > 0:
        ghidfalau_net_fuel = max(0, ghidfalau_total_fuel - mc_values['consum_extra_ghidfalau'])

    basis_labels = {
        'mc_exploatati': 'TOTAL BALAST EXPLOATAȚI',
        'mc_balast_sortati': 'TOTAL BALAST SORTAT',
        'mc_stoc_statie': 'STOC TOTAL BALAST STAȚIE',
        'mc_cap_tractor': 'TRANSP. CAP TRACTOR',
        'total_mc_vanduti': 'TOTAL VÂNDUȚI SORT + BALAST',
        'mc_balast': 'TOTAL BALAST VÂNDUT',
        'mc_sorturi_vanduti': 'TOTAL SORTURI VÂNDUȚI',
        'nisip_exploatat_ghidfalau': 'NISIP EXPLOATAT GHIDFALĂU',
        'nisip_transportat_budila': 'NISIP TRANSPORTAT LA BUDILA'
    }

    return render_template('analysis.html', 
                         mc_values=mc_values, 
                         budila_data=budila_data,
                         ghidfalau_data=ghidfalau_data,
                         ghidfalau_total_fuel=ghidfalau_total_fuel,
                         ghidfalau_net_fuel=ghidfalau_net_fuel,
                         total_engine_fuel=total_engine_fuel,
                         net_engine_fuel=net_engine_fuel,
                         start_date=start_date_str,
                         end_date=end_date_str,
                         all_categories=all_categories,
                         visible_categories=visible_categories,
                         basis_labels=basis_labels,
                         exclude_hidden=exclude_hidden,
                         calc_basis=calc_basis)


@app.route('/analysis/settings', methods=['POST'])
def analysis_settings():
    from models import AppSettings
    import json
    
    gid = session.get('gestiune_id')
    if not gid:
        return redirect('/select-profile')
        
    visible = request.form.getlist('visible_categories')
    exclude_hidden = request.form.get('exclude_hidden') == 'on'
    
    # Save visible categories
    setting = AppSettings.query.filter_by(key='analysis_visible_categories', gestiune_id=gid).first()
    if not setting:
        setting = AppSettings(key='analysis_visible_categories', value=json.dumps(visible), gestiune_id=gid)
        db.session.add(setting)
    else:
        setting.value = json.dumps(visible)
        
    # Save exclude toggle
    setting_toggle = AppSettings.query.filter_by(key='analysis_exclude_hidden', gestiune_id=gid).first()
    if not setting_toggle:
        setting_toggle = AppSettings(key='analysis_exclude_hidden', value='1' if exclude_hidden else '0', gestiune_id=gid)
        db.session.add(setting_toggle)
    else:
        setting_toggle.value = '1' if exclude_hidden else '0'
        
    db.session.commit()
    flash("Preferințele de afișare au fost salvate.", "success")
    
    # Pass back filters
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    return redirect(url_for('analysis_page', start=start, end=end))


@app.route('/analysis/save-basis', methods=['POST'])
def save_analysis_basis():
    from models import AppSettings
    gid = session.get('gestiune_id')
    if not gid:
        return {"status": "error", "message": "No session"}, 401
        
    basis = request.json.get('basis')
    cat_name = request.json.get('category')
    
    if not basis:
        return {"status": "error", "message": "No basis provided"}, 400
        
    key = f'analysis_basis_cat_{cat_name}' if cat_name else 'analysis_calculation_basis'
    
    setting = AppSettings.query.filter_by(key=key, gestiune_id=gid).first()
    if not setting:
        setting = AppSettings(key=key, value=basis, gestiune_id=gid)
        db.session.add(setting)
    else:
        setting.value = basis
        
    db.session.commit()
    return {"status": "success", "basis": basis, "category": cat_name}


@app.route('/admin/analysis_pdf')
def analysis_pdf():
    from models import VehicleCategory, Transaction, Vehicle, AppSettings, Gestiune
    from sqlalchemy import func
    from services import generate_analysis_report_pdf
    import json
    
    gid = session.get('gestiune_id')
    if not gid:
        return redirect('/select-profile')
        
    start_date_str = request.args.get('start')
    end_date_str = request.args.get('end')
    print(f"DEBUG PDF: {start_date_str} to {end_date_str}")
    
    if not start_date_str or not end_date_str:
        return "Parametri incorecți", 400

    def parse_dt(dt_str):
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None

    start_date = parse_dt(start_date_str)
    end_date = parse_dt(end_date_str)

    if not start_date or not end_date:
        return f"Format dată invalid: {start_date_str}", 400

    # Get settings (same as analysis_page)
    visible_setting = AppSettings.query.filter_by(key='analysis_visible_categories', gestiune_id=gid).first()
    if visible_setting and visible_setting.value:
        try: visible_categories = json.loads(visible_setting.value)
        except: visible_categories = []
    else: visible_categories = []

    exclude_setting = AppSettings.query.filter_by(key='analysis_exclude_hidden', gestiune_id=gid).first()
    exclude_hidden = (exclude_setting.value == '1') if exclude_setting else False

    # Get basis settings
    basis_setting = AppSettings.query.filter_by(key='analysis_calculation_basis', gestiune_id=gid).first()
    calc_basis = basis_setting.value if basis_setting else 'total_mc_vanduti'
    
    cat_basis_settings = AppSettings.query.filter(AppSettings.key.like('analysis_basis_cat_%'), AppSettings.gestiune_id == gid).all()
    cat_basis_map = {s.key.replace('analysis_basis_cat_', ''): s.value for s in cat_basis_settings}

    # MC values logic (v5.5 + v5.6)
    mc_keys = [
        'total_mc_vanduti', 'mc_balast', 'mc_exploatati', 
        'mc_balast_sortati', 'mc_pe_statie', 'to_cap_tractor',
        'consum_extra_8x4', 'mc_stoc_statie', 'mc_cap_tractor',
        'nisip_exploatat_ghidfalau', 'nisip_transportat_budila',
        'consum_extra_ghidfalau'
    ]
    mc_values = {k: 0.0 for k in mc_keys}
    for key in mc_keys:
        setting = AppSettings.query.filter_by(key=f'analysis_{key}', gestiune_id=gid).first()
        try: val = float(setting.value) if setting and setting.value else 0.0
        except: val = 0.0
        mc_values[key] = val
        
    mc_values['mc_sorturi_vanduti'] = mc_values['total_mc_vanduti'] - mc_values['mc_balast']
    mc_values['mc_stoc_statie'] = mc_values['mc_exploatati'] - mc_values['mc_balast_sortati']
    if mc_values['to_cap_tractor'] > 0:
        mc_values['mc_cap_tractor'] = mc_values['to_cap_tractor'] / 1.5

    # Fetch stats
    stats = db.session.query(
        VehicleCategory.name,
        func.sum(Transaction.quantity).label('total_fuel')
    ).join(Vehicle, Transaction.vehicle_id == Vehicle.id)\
     .join(VehicleCategory, Vehicle.category_id == VehicleCategory.id)\
     .filter(Transaction.gestiune_id == gid, Transaction.date >= start_date, Transaction.date <= end_date)\
     .group_by(VehicleCategory.name).all()
    
    consumption_map = {name: fuel for name, fuel in stats}
    all_categories = VehicleCategory.query.filter_by(gestiune_id=gid).all()
    
    budila_data = []
    ghidfalau_data = []
    
    for cat_obj in all_categories:
        if visible_categories and cat_obj.name not in visible_categories:
            continue
            
        fuel = consumption_map.get(cat_obj.name, 0)
        name_upper = cat_obj.name.upper()
        is_ghidfalau = any(kw in name_upper for kw in ['GHID', 'GHIDFALAU', 'GHIDFALĂU'])
        
        default_basis = 'nisip_exploatat_ghidfalau' if is_ghidfalau else 'total_mc_vanduti'
        basis = cat_basis_map.get(cat_obj.name, default_basis)
        
        # Calculate individual efficiency for PDF table
        mc_denom = mc_values.get(basis, 0)
        eff = fuel / mc_denom if mc_denom > 0 else 0
        
        record = {
            'category': cat_obj.name,
            'fuel': fuel,
            'basis': basis,
            'mc_val': mc_denom,
            'efficiency': eff
        }
        
        if is_ghidfalau:
            ghidfalau_data.append(record)
        else:
            budila_data.append(record)

    # Totals (Consistent with dashboard)
    ghidfalau_total_fuel = sum(item['fuel'] for item in ghidfalau_data)
    
    if exclude_hidden and visible_categories:
        total_engine_fuel = sum(fuel for name, fuel in stats 
                              if name in visible_categories and not any(kw in name.upper() for kw in ['GHID', 'GHIDFALAU', 'GHIDFALĂU']))
    else:
        total_engine_fuel = sum(fuel for name, fuel in stats 
                              if not any(kw in name.upper() for kw in ['GHID', 'GHIDFALAU', 'GHIDFALĂU']))
    
    net_engine_fuel = total_engine_fuel
    if mc_values.get('consum_extra_8x4', 0) > 0:
        net_engine_fuel = max(0, total_engine_fuel - mc_values['consum_extra_8x4'])

    ghidfalau_net_fuel = ghidfalau_total_fuel
    if mc_values.get('consum_extra_ghidfalau', 0) > 0:
        ghidfalau_net_fuel = max(0, ghidfalau_total_fuel - mc_values['consum_extra_ghidfalau'])

    basis_labels = {
        'mc_exploatati': 'TOTAL BALAST EXPLOATAȚI',
        'mc_balast_sortati': 'TOTAL BALAST SORTAT',
        'mc_stoc_statie': 'STOC TOTAL BALAST STAȚIE',
        'mc_cap_tractor': 'TRANSP. CAP TRACTOR',
        'total_mc_vanduti': 'TOTAL VÂNDUȚI SORT + BALAST',
        'mc_balast': 'TOTAL BALAST VÂNDUT',
        'mc_sorturi_vanduti': 'TOTAL SORTURI VÂNDUȚI',
        'nisip_exploatat_ghidfalau': 'NISIP EXPLOATAT GHIDFALĂU',
        'nisip_transportat_budila': 'NISIP TRANSPORTAT LA BUDILA'
    }

    def clean_accents(text):
        if not text: return ""
        if not isinstance(text, str): text = str(text)
        import unicodedata
        return "".join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

    # Calculate final scores
    gen_mc_vanduti = mc_values.get('total_mc_vanduti', 0)
    eff_vanduti = net_engine_fuel / gen_mc_vanduti if gen_mc_vanduti > 0 else 0
    
    gen_mc_sortati = mc_values.get('mc_balast_sortati', 0)
    eff_sortati = total_engine_fuel / gen_mc_sortati if gen_mc_sortati > 0 else 0
    
    gen_mc_ghid = mc_values.get('nisip_exploatat_ghidfalau', 0)
    eff_ghid = ghidfalau_net_fuel / gen_mc_ghid if gen_mc_ghid > 0 else 0


    # Prep data for PDF
    def prep_list(data_list):
        cleaned = []
        for item in data_list:
            cleaned.append({
                'category': clean_accents(item['category']),
                'fuel': item['fuel'],
                'basis_name': clean_accents(basis_labels.get(item['basis'], item['basis'])),
                'mc_val': item['mc_val'],
                'efficiency': item['efficiency']
            })
        return cleaned

    gestiune = Gestiune.query.get(gid)
    logo_base64 = None
    if gestiune.logo_path and not ('profile_logos/1.jpg' in gestiune.logo_path or gestiune.logo_path == '1.jpg'):
        logo_abs_path = os.path.join(app.root_path, gestiune.logo_path.replace('/', os.sep)) if gestiune.logo_path.startswith('static/') else os.path.join(DATA_DIR, 'logos', gestiune.logo_path.replace('/', os.sep))
        if os.path.exists(logo_abs_path):
            import base64
            try:
                with open(logo_abs_path, "rb") as img_file:
                    ext = os.path.splitext(logo_abs_path)[1][1:]
                    logo_base64 = f"data:image/{ext};base64,{base64.b64encode(img_file.read()).decode()}"
            except: pass

    # Global scores for Summary
    gen_mc_vanduti = mc_values.get('total_mc_vanduti', 0)
    eff_vanduti = total_engine_fuel / gen_mc_vanduti if gen_mc_vanduti > 0 else 0
    
    gen_mc_sortati = mc_values.get('mc_balast_sortati', 0)
    eff_sortati = total_engine_fuel / gen_mc_sortati if gen_mc_sortati > 0 else 0

    ghidfalau_net_fuel = ghidfalau_total_fuel
    extra_ghid = mc_values.get('consum_extra_ghidfalau', 0)
    if extra_ghid > 0:
        ghidfalau_net_fuel = max(0, ghidfalau_total_fuel - extra_ghid)

    gen_mc_ghid = mc_values.get('nisip_exploatat_ghidfalau', 0)
    eff_ghid = ghidfalau_net_fuel / gen_mc_ghid if gen_mc_ghid > 0 else 0

    html = render_template('analysis_pdf.html',
                         gestiune_name=clean_accents(gestiune.name),
                         logo_base64=logo_base64,
                         start_date=start_date.strftime('%d.%m.%Y'),
                         end_date=end_date.strftime('%d.%m.%Y'),
                         total_fuel_budila=total_engine_fuel,
                         total_fuel_ghid=ghidfalau_total_fuel,
                         net_fuel=net_engine_fuel,
                         mc_vanduti=gen_mc_vanduti,
                         mc_sortati=gen_mc_sortati,
                         mc_ghid=gen_mc_ghid,
                         eff_vanduti=eff_vanduti,
                         eff_sortati=eff_sortati,
                         eff_ghid=eff_ghid,
                         budila_data=prep_list(budila_data),
                         ghidfalau_data=prep_list(ghidfalau_data),
                         generated_at=datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
    
    
    # ... (Preceding HTML generation logic) ...
    
    
    
    pdf_path, msg = generate_analysis_report_pdf(html, gid)
    if pdf_path:
        return jsonify({'status': 'success', 'filepath': pdf_path, 'filename': os.path.basename(pdf_path)})
        
    return jsonify({'status': 'error', 'message': msg}), 500


@app.route('/admin')
def admin_page():
    from models import Company, Vehicle, Transaction, VehicleCategory, AppSettings
    
    gid = session.get('gestiune_id')
    
    companies = Company.query.filter_by(gestiune_id=gid).order_by(Company.name).all()
    vehicles = Vehicle.query.filter_by(gestiune_id=gid).order_by(Vehicle.plate_number).all()
    categories = VehicleCategory.query.filter_by(gestiune_id=gid).order_by(VehicleCategory.name).all()
    
    # Vehicles with no company (BEFORE filtering)
    unallocated_vehicles = [v for v in vehicles if v.company_id is None]
    
    # Vehicles with no category (BEFORE filtering)
    uncategorized_vehicles = [v for v in vehicles if v.category_id is None]
    
    # Optional: Filter vehicles for the company view
    c_id = request.args.get('company_id', type=int)
    if c_id:
        vehicles = [v for v in vehicles if v.company_id == c_id]
    
    # Stats for unallocated transactions
    unallocated_count = Transaction.query.filter_by(company_id=None, gestiune_id=gid).count()
    
    # Get custom capacities
    custom_capacities = {}
    settings = AppSettings.query.filter(AppSettings.key.like('tank_capacity_%'), AppSettings.gestiune_id == gid).all()
    for s in settings:
        try:
            c_id_match = s.key.split('_')[-1]
            custom_capacities[int(c_id_match)] = float(s.value)
        except: continue

    return render_template('admin.html', 
                         companies=companies, 
                         vehicles=vehicles, 
                         categories=categories,
                         unallocated_vehicles=unallocated_vehicles,
                         uncategorized_vehicles=uncategorized_vehicles,
                         unallocated_count=unallocated_count,
                         custom_capacities=custom_capacities,
                         active_tab=request.args.get('tab'))


@app.route('/admin/company/delete_logo/<int:id>')
def delete_company_logo(id):
    from models import Company
    import os
    
    # Check for logo files in AppData
    logo_dir = os.path.join(DATA_DIR, 'logos', 'company_logos')
    for ext in ['png', 'jpg']:
        path = os.path.join(logo_dir, f"{id}.{ext}")
        if os.path.exists(path):
            try:
                os.remove(path)
                flash('Logo-ul a fost șters cu succes.', 'success')
            except Exception as e:
                flash(f'Eroare la ștergerea logo-ului: {str(e)}', 'danger')
                
    return redirect(f'/admin/company/edit/{id}')


@app.route('/admin/vehicle/move/<int:id>', methods=['GET', 'POST'])
def move_vehicle(id):
    from models import Vehicle, Company, Transaction
    gid = session.get('gestiune_id')
    v = Vehicle.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    old_company = v.company_id
    
    if request.method == 'POST':
        new_comp_id = request.form.get('new_company_id')
        if new_comp_id:
            v.company_id = int(new_comp_id)
            
            # CASCADE: Update all existing transactions for this vehicle
            Transaction.query.filter_by(
                vehicle_id=v.id,
                gestiune_id=gid
            ).update({Transaction.company_id: int(new_comp_id)})
            
            db.session.commit()
            
            if old_company:
                 return redirect(f'/admin?company_id={old_company}')
            else:
                 return redirect('/admin?tab=unallocated')
                 
        return redirect('/admin')
        
    companies = Company.query.filter_by(gestiune_id=gid).all()
    return render_template('move_vehicle.html', vehicle=v, companies=companies)

@app.route('/admin/company/new', methods=['GET', 'POST'])
def new_company():
    from models import Company
    gid = session.get('gestiune_id')
    if request.method == 'POST':
        name = request.form['name']
        cui = request.form.get('cui')
        address = request.form.get('address')
        product_code = request.form.get('product_code')
        
        # Check for duplicate in this gestiune
        if Company.query.filter_by(name=name, gestiune_id=gid).first():
            flash(f"Firma '{name}' există deja în această gestiune.", "danger")
            return redirect('/admin')
            
        c = Company(
            name=name,
            cui=cui,
            address=address,
            product_code=product_code,
            gestiune_id=gid
        )
        db.session.add(c)
        db.session.commit()
        flash("Firma a fost creată.", "success")
        
        # Handle Logo Upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                try:
                    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
                    if ext in ['png', 'jpg', 'jpeg']:
                        if ext == 'jpeg': ext = 'jpg'
                        # Clean old
                        logo_dir = os.path.join(DATA_DIR, 'logos', 'company_logos')
                        if not os.path.exists(logo_dir):
                            os.makedirs(logo_dir)
                            
                        for old_ext in ['png', 'jpg']:
                            old_path = os.path.join(logo_dir, f"{c.id}.{old_ext}")
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        
                        save_path = os.path.join(logo_dir, f"{c.id}.{ext}")
                        file.save(save_path)
                except Exception as e:
                    flash(f"Eroare salvare logo: {str(e)}", "warning")
                    
        return redirect(f'/admin?company_id={c.id}')
    return render_template('company_form.html', company=None)

@app.route('/admin/company/edit/<int:id>', methods=['GET', 'POST'])
def edit_company(id):
    from models import Company
    gid = session.get('gestiune_id')
    c = Company.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    if request.method == 'POST':
        c.name = request.form['name']
        c.cui = request.form.get('cui')
        c.address = request.form.get('address')
        c.product_code = request.form.get('product_code')
        db.session.commit()
        flash("Informațiile firmei au fost actualizate.", "success")
        
        # Handle Logo Upload
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                try:
                    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
                    if ext in ['png', 'jpg', 'jpeg']:
                        if ext == 'jpeg': ext = 'jpg'
                        # Clean old
                        logo_dir = os.path.join(DATA_DIR, 'logos', 'company_logos')
                        if not os.path.exists(logo_dir):
                            os.makedirs(logo_dir)

                        for old_ext in ['png', 'jpg']:
                            old_path = os.path.join(logo_dir, f"{c.id}.{old_ext}")
                            if os.path.exists(old_path):
                                os.remove(old_path)
                        
                        save_path = os.path.join(logo_dir, f"{c.id}.{ext}")
                        file.save(save_path)
                except Exception as e:
                    flash(f"Eroare salvare logo: {str(e)}", "warning")

        return redirect(f'/admin?company_id={c.id}')
    
    logo_url = None
    logo_dir = os.path.join(DATA_DIR, 'logos', 'company_logos')
    if os.path.exists(os.path.join(logo_dir, f"{c.id}.png")):
        logo_url = url_for('user_content', filename=f"company_logos/{c.id}.png")
    elif os.path.exists(os.path.join(logo_dir, f"{c.id}.jpg")):
        logo_url = url_for('user_content', filename=f"company_logos/{c.id}.jpg")
        
    return render_template('company_form.html', company=c, logo_url=logo_url)

@app.route('/admin/vehicle/new', methods=['GET', 'POST'])
def new_vehicle():
    from models import Vehicle, Company, VehicleCategory
    gid = session.get('gestiune_id')
    companies = Company.query.filter_by(gestiune_id=gid).all()
    categories = VehicleCategory.query.filter_by(gestiune_id=gid).order_by(VehicleCategory.name).all()
    if request.method == 'POST':
        plate = request.form['plate_number'].upper().strip()
        
        if not plate:
            flash("Numărul de înmatriculare este obligatoriu.", "danger")
            return redirect('/admin')

        existing = Vehicle.query.filter_by(plate_number=plate, gestiune_id=gid).first()
        
        if existing:
            if not existing.company_id:
                flash(f"Mașina {plate} se află deja la secțiunea 'Mașini nealocate'!", "warning")
                return redirect('/admin?tab=unallocated')
            else:
                flash(f"Mașina {plate} există deja alocată la firma: {existing.company.name}.", "info")
                return redirect(f'/admin?company_id={existing.company.id}')

        comp_id = request.form.get('company_id')
        cat_id = request.form.get('category_id')
        v = Vehicle(
            plate_number=plate,
            company_id=int(comp_id) if comp_id else None,
            category_id=int(cat_id) if cat_id else None,
            gestiune_id=gid
        )
        db.session.add(v)
        db.session.commit()
        flash("Vehiculul a fost adăugat.", "success")
        
        if v.company_id:
             return redirect(f'/admin?company_id={v.company_id}')
        return redirect('/admin?tab=unallocated')
        
    return render_template('vehicle_form.html', vehicle=None, companies=companies, categories=categories)

@app.route('/admin/vehicle/edit/<int:id>', methods=['GET', 'POST'])
def edit_vehicle(id):
    from models import Vehicle, Company, VehicleCategory, Transaction
    gid = session.get('gestiune_id')
    v = Vehicle.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    companies = Company.query.filter_by(gestiune_id=gid).all()
    categories = VehicleCategory.query.filter_by(gestiune_id=gid).order_by(VehicleCategory.name).all()
    if request.method == 'POST':
        v.plate_number = request.form['plate_number'].upper()
        comp_id = request.form.get('company_id')
        cat_id = request.form.get('category_id')
        
        new_company_id = int(comp_id) if comp_id else None
        
        # CASCADE: Update all existing transactions for this vehicle if company changed
        if v.company_id != new_company_id:
            Transaction.query.filter_by(
                vehicle_id=v.id,
                gestiune_id=gid
            ).update({Transaction.company_id: new_company_id})
        
        v.company_id = new_company_id
        v.category_id = int(cat_id) if cat_id else None
        db.session.commit()
        
        if v.company_id:
             return redirect(f'/admin?company_id={v.company_id}')
        return redirect('/admin?tab=unallocated')
    return render_template('vehicle_form.html', vehicle=v, companies=companies, categories=categories)

@app.route('/reports/download/<path:filename>')
def download_report(filename):
    """Serve report files for the manual download button."""
    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(".")
        reports_dir = os.path.join(base_dir, "reports")
        return send_from_directory(reports_dir, filename, as_attachment=True)
    except Exception as e:
        return f"Error: {e}", 404

def open_native_file(filepath):
    """Open file with system default viewer if on Windows and local."""
    try:
        import platform
        import subprocess
        
        if platform.system() == 'Windows':
            os.startfile(filepath)
            return True
        elif platform.system() == 'Darwin':
            subprocess.call(('open', filepath))
            return True
        elif platform.system() == 'Linux':
            subprocess.call(('xdg-open', filepath))
            return True
    except Exception as e:
        print(f"Native open failed: {e}")
    return False

@app.route('/admin/report', methods=['POST'])
def generate_report():
    from services import generate_pdf_report
    import os
    
    gid = session.get('gestiune_id')
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    company_id = request.form.get('company_id')
    bon_number = request.form.get('bon_number', '')
    
    

    
    if company_id:
        try:
            company_id = int(company_id)
            # Save report interval for this company
            from models import Company
            from datetime import datetime
            
            c = Company.query.filter_by(id=company_id, gestiune_id=gid).first()
            if c:
                try:
                    c.last_report_start = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
                    c.last_report_end = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
                    db.session.commit()
                except ValueError:
                    pass # Ignore date parsing errors
                    
        except ValueError:
            company_id = None
        
    filepath, message = generate_pdf_report(start_date, end_date, gid, company_id, bon_number)
    
    if filepath:
        return jsonify({'status': 'success', 'filepath': filepath, 'filename': os.path.basename(filepath), 'message': message})
    else:
        return jsonify({'status': 'error', 'message': message})

@app.route('/admin/generate_monthly_report', methods=['POST'])
def generate_monthly_report():
    from services import generate_monthly_report_pdf
    import os
    
    gid = session.get('gestiune_id')
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    
    
    
    initial_series = request.form.get('initial_series')
    final_series = request.form.get('final_series')
    
    if initial_series: initial_series = float(initial_series)
    if final_series: final_series = float(final_series)
    
    filepath, message = generate_monthly_report_pdf(start_date, end_date, gid, initial_series, final_series)
    
    if filepath:
        return jsonify({'status': 'success', 'filepath': filepath, 'filename': os.path.basename(filepath), 'message': message})
    else:
        return jsonify({'status': 'error', 'message': message})

@app.route('/admin/undo')
def undo_action():
    from services import HistoryService
    gid = session.get('gestiune_id')
    success, message = HistoryService.undo(gid)
    category = 'success' if success else 'warning'
    flash(message, category)
    return redirect(request.referrer or '/')

@app.route('/admin/redo')
def redo_action():
    from services import HistoryService
    gid = session.get('gestiune_id')
    success, message = HistoryService.redo(gid)
    category = 'success' if success else 'warning'
    flash(message, category)
    return redirect(request.referrer or '/')


# ============= SHUTDOWN ENDPOINT =============
@app.route('/api/shutdown', methods=['POST'])
def shutdown_server():
    """Gracefully shutdown the Flask server"""
    import os
    import signal
    
    # Kill the current process
    pid = os.getpid()
    os.kill(pid, signal.SIGTERM)
    
    return jsonify({'status': 'shutting down'}), 200

@app.route('/api/set-theme', methods=['POST'])
def set_theme_api():
    from models import AppSettings
    gid = session.get('gestiune_id')
    if not gid:
        return jsonify({'status': 'error', 'message': 'No active session'}), 401
    data = request.json
    theme = data.get('theme', 'light')
    setting = AppSettings.query.filter_by(key='app_theme', gestiune_id=gid).first()
    if not setting:
        setting = AppSettings(key='app_theme', value=theme, gestiune_id=gid)
        db.session.add(setting)
    else:
        setting.value = theme
    db.session.commit()
    return jsonify({'status': 'success', 'theme': theme})

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """Update heartbit timestamp to keep server alive"""
    global last_heartbeat
    last_heartbeat = time.time()
    return jsonify({'status': 'alive'}), 200



@app.route('/admin/database/import', methods=['POST'])
def import_database():
    """Import data from an SQLite backup, FULLY REPLACING the active profile's data."""
    if 'db_file' not in request.files:
        flash('Nici un fișier selectat.', 'danger')
        return redirect('/data-management')
    
    file = request.files['db_file']
    if file.filename == '':
        flash('Nici un fișier selectat.', 'danger')
        return redirect('/data-management')

    gid = session.get('gestiune_id')
    if not gid:
        flash('Nu există nici o gestiune activă selectată!', 'danger')
        return redirect('/select-profile')

    if not file or not (file.filename.endswith('.db') or file.filename.endswith('.sqlite')):
        flash('Fișier nevalid. Doar .db și .sqlite sunt acceptate.', 'danger')
        return redirect('/data-management')

    import sqlite3
    import tempfile
    import time as time_module
    from models import Company, Vehicle, Transaction, StockOperation, VehicleCategory, AppSettings
    from datetime import datetime
    
    global BUSY_MODE
    BUSY_MODE = True
    
    # Save uploaded file to temp location
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"import_{int(time_module.time())}.db")
    file.save(temp_path)
    
    src_conn = None
    try:
        # Validate SQLite header
        with open(temp_path, 'rb') as f:
            header = f.read(16)
        if not header.startswith(b'SQLite format 3'):
            flash('Fișierul încărcat nu este o bază de date SQLite validă!', 'danger')
            return redirect('/data-management')
        
        # Connect to uploaded database
        src_conn = sqlite3.connect(temp_path)
        src_cursor = src_conn.cursor()
        
        print(f"[IMPORT] Starting FULL OVERWRITE import into gestiune_id={gid}")
        
        # --- Helper functions ---
        def get_columns(table_name):
            try:
                src_cursor.execute(f"PRAGMA table_info([{table_name}])")
                return [info[1] for info in src_cursor.fetchall()]
            except Exception:
                return []

        def table_exists(table_name):
            src_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            return src_cursor.fetchone() is not None

        def parse_sqlite_date(d_str):
            if not d_str: return datetime.utcnow()
            try: return datetime.strptime(d_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
            except Exception:
                try: return datetime.strptime(d_str, '%Y-%m-%d')
                except Exception: return datetime.utcnow()

        def build_gestiune_filter(table_name):
            """Build WHERE clause for gestiune_id filtering in source DB."""
            cols = get_columns(table_name)
            if 'gestiune_id' in cols:
                # Find the source gestiune_id to filter by
                # If source has gestiune table, pick the first one; otherwise filter by any
                src_gid = detect_source_gestiune_id()
                if src_gid is not None:
                    return f" WHERE gestiune_id = {src_gid}"
                # If we can't detect, import everything (old single-profile backup)
            return ""

        def detect_source_gestiune_id():
            """Detect the gestiune_id in the source backup file."""
            if not hasattr(detect_source_gestiune_id, '_cached'):
                detect_source_gestiune_id._cached = None
                try:
                    if table_exists('gestiune'):
                        src_cursor.execute("SELECT id FROM gestiune LIMIT 1")
                        row = src_cursor.fetchone()
                        if row:
                            detect_source_gestiune_id._cached = row[0]
                    else:
                        # No gestiune table = old single-profile DB, no filtering needed
                        detect_source_gestiune_id._cached = None
                except Exception:
                    detect_source_gestiune_id._cached = None
            return detect_source_gestiune_id._cached

        # ============================================================
        # PHASE 1: DELETE all existing data for the active profile
        # (Order: most dependent first → least dependent last)
        # ============================================================
        print(f"[IMPORT] Phase 1: Deleting existing data for gestiune_id={gid}")
        
        # Delete transactions first (depends on vehicles + companies)
        Transaction.query.filter_by(gestiune_id=gid).delete()
        # Delete stock operations (depends on companies)
        StockOperation.query.filter_by(gestiune_id=gid).delete()
        # Delete vehicles (depends on companies + categories)
        Vehicle.query.filter_by(gestiune_id=gid).delete()
        # Delete companies
        Company.query.filter_by(gestiune_id=gid).delete()
        # Delete categories
        VehicleCategory.query.filter_by(gestiune_id=gid).delete()
        # Delete app settings for this profile
        AppSettings.query.filter_by(gestiune_id=gid).delete()
        
        db.session.flush()
        print(f"[IMPORT] Phase 1 complete: All existing data for profile deleted")

        # ============================================================
        # PHASE 2: INSERT new data from the backup file
        # ============================================================
        company_map = {}   # src_id -> new_id
        category_map = {}  # src_id -> new_id
        vehicle_map = {}   # src_id -> new_id
        counts = {"categories": 0, "companies": 0, "vehicles": 0, "stock": 0, "trans": 0, "settings": 0}

        # 1. Import Categories
        if table_exists("vehicle_category"):
            cols = get_columns("vehicle_category")
            where = build_gestiune_filter("vehicle_category")
            
            select_cols = ["id", "name"]
            if "description" in cols: select_cols.append("description")
            if "icon" in cols: select_cols.append("icon")
            
            src_cursor.execute(f"SELECT {', '.join(select_cols)} FROM vehicle_category{where}")
            for row in src_cursor.fetchall():
                r = dict(zip(select_cols, row))
                new_cat = VehicleCategory(
                    name=r['name'],
                    description=r.get('description'),
                    icon=r.get('icon', 'bi-tag-fill'),
                    gestiune_id=gid
                )
                db.session.add(new_cat)
                db.session.flush()
                category_map[r['id']] = new_cat.id
                counts["categories"] += 1

        # 2. Import Companies
        if table_exists("company"):
            cols = get_columns("company")
            where = build_gestiune_filter("company")
            
            select_cols = ["id", "name"]
            for c in ["cui", "address", "product_code"]:
                if c in cols: select_cols.append(c)
            
            src_cursor.execute(f"SELECT {', '.join(select_cols)} FROM company{where}")
            for row in src_cursor.fetchall():
                r = dict(zip(select_cols, row))
                new_comp = Company(
                    name=r['name'],
                    cui=r.get('cui'),
                    address=r.get('address'),
                    product_code=r.get('product_code'),
                    gestiune_id=gid
                )
                db.session.add(new_comp)
                db.session.flush()
                company_map[r['id']] = new_comp.id
                counts["companies"] += 1

        # 3. Import Vehicles
        if table_exists("vehicle"):
            cols = get_columns("vehicle")
            where = build_gestiune_filter("vehicle")
            
            select_cols = ["id", "plate_number"]
            if "company_id" in cols: select_cols.append("company_id")
            if "category_id" in cols: select_cols.append("category_id")
            
            src_cursor.execute(f"SELECT {', '.join(select_cols)} FROM vehicle{where}")
            for row in src_cursor.fetchall():
                r = dict(zip(select_cols, row))
                new_veh = Vehicle(
                    plate_number=r['plate_number'],
                    company_id=company_map.get(r.get('company_id')),
                    category_id=category_map.get(r.get('category_id')),
                    gestiune_id=gid
                )
                db.session.add(new_veh)
                db.session.flush()
                vehicle_map[r['id']] = new_veh.id
                counts["vehicles"] += 1

        # 4. Import Stock Operations
        if table_exists("stock_operation"):
            cols = get_columns("stock_operation")
            where = build_gestiune_filter("stock_operation")
            
            select_cols = ["operation_type", "quantity", "date"]
            if "description" in cols: select_cols.append("description")
            if "company_id" in cols: select_cols.append("company_id")
            
            src_cursor.execute(f"SELECT {', '.join(select_cols)} FROM stock_operation{where}")
            for row in src_cursor.fetchall():
                r = dict(zip(select_cols, row))
                new_op = StockOperation(
                    operation_type=r['operation_type'],
                    quantity=r['quantity'],
                    date=parse_sqlite_date(r['date']),
                    description=r.get('description'),
                    company_id=company_map.get(r.get('company_id')),
                    gestiune_id=gid
                )
                db.session.add(new_op)
                counts["stock"] += 1
            db.session.flush()

        # 5. Import Transactions
        if table_exists("transaction"):
            cols = get_columns("transaction")
            where = build_gestiune_filter("transaction")
            
            select_cols = ["date", "vehicle_id", "company_id", "quantity"]
            
            src_cursor.execute(f"SELECT {', '.join(select_cols)} FROM [transaction]{where}")
            for row in src_cursor.fetchall():
                r = dict(zip(select_cols, row))
                new_veh_id = vehicle_map.get(r['vehicle_id'])
                if not new_veh_id:
                    continue  # Skip orphaned transactions
                
                new_trans = Transaction(
                    date=parse_sqlite_date(r['date']),
                    vehicle_id=new_veh_id,
                    company_id=company_map.get(r['company_id']),
                    quantity=r['quantity'],
                    gestiune_id=gid
                )
                db.session.add(new_trans)
                counts["trans"] += 1
            db.session.flush()

        # 6. Import App Settings
        if table_exists("app_settings"):
            cols = get_columns("app_settings")
            where = build_gestiune_filter("app_settings")
            
            src_cursor.execute(f"SELECT key, value FROM app_settings{where}")
            for row in src_cursor.fetchall():
                new_setting = AppSettings(
                    key=row[0],
                    value=row[1],
                    gestiune_id=gid
                )
                db.session.add(new_setting)
                counts["settings"] += 1
            db.session.flush()

        # ============================================================
        # PHASE 3: COMMIT
        # ============================================================
        db.session.commit()
        
        print(f"[IMPORT] Phase 2 complete: {counts}")
        
        msg = (f"Import reușit! Profilul a fost restaurat complet. "
               f"Importate: {counts['categories']} categorii, {counts['companies']} companii, "
               f"{counts['vehicles']} vehicule, {counts['stock']} op. stoc, "
               f"{counts['trans']} tranzacții, {counts['settings']} setări.")
        flash(msg, 'success')
        return redirect('/data-management')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Eroare fatală la import: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
        return redirect('/data-management')
    finally:
        if src_conn:
            try: src_conn.close()
            except Exception: pass
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except Exception: pass
            
        BUSY_MODE = False













                







            

    

@app.route('/admin/vehicle/set_category/<int:id>', methods=['POST'])
def set_vehicle_category(id):
    from models import Vehicle
    gid = session.get('gestiune_id')
    v = Vehicle.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    cat_id = request.form.get('category_id')
    v.category_id = int(cat_id) if cat_id else None
    db.session.commit()
    flash(f"Categoria pentru {v.plate_number} a fost actualizată.", "success")
    # Consistently use categories tab
    return redirect(url_for('admin_page', tab='categories'))

@app.route('/admin/vehicles/bulk_set_category', methods=['POST'])
def bulk_set_vehicle_category():
    from models import Vehicle
    gid = session.get('gestiune_id')
    vehicle_ids = request.form.getlist('vehicle_ids')
    cat_id = request.form.get('category_id')
    
    if not vehicle_ids:
        flash("Nu ați selectat nici un vehicul.", "warning")
        return redirect(url_for('admin_page', tab='categories'))
    
    try:
        new_cat_id = int(cat_id) if cat_id else None
        updated_count = 0
        for vid in vehicle_ids:
            v = Vehicle.query.filter_by(id=int(vid), gestiune_id=gid).first()
            if v:
                v.category_id = new_cat_id
                updated_count += 1
        
        db.session.commit()
        flash(f"Am actualizat categoria pentru {updated_count} vehicule.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Eroare la actualizarea în masă: {str(e)}", "danger")
        
    return redirect(url_for('admin_page', tab='categories'))

@app.route('/admin/vehicles/bulk_set_company', methods=['POST'])
def bulk_set_vehicle_company():
    from models import Vehicle, Transaction
    gid = session.get('gestiune_id')
    vehicle_ids = request.form.getlist('vehicle_ids')
    target_company_id = request.form.get('target_company_id')

    if not vehicle_ids:
        flash('Niciun vehicul selectat.', 'warning')
        return redirect(url_for('admin_page', tab='unallocated'))

    if not target_company_id:
        flash('Vă rugăm să selectați o companie.', 'warning')
        return redirect(url_for('admin_page', tab='unallocated'))

    try:
        target_company_id = int(target_company_id)
        count = 0
        for vid in vehicle_ids:
            vehicle = Vehicle.query.filter_by(id=int(vid), gestiune_id=gid).first()
            if vehicle:
                vehicle.company_id = target_company_id
                
                # CASCADE: Update all existing transactions for this vehicle in this gestiune
                Transaction.query.filter_by(
                    vehicle_id=vehicle.id,
                    gestiune_id=gid
                ).update({Transaction.company_id: target_company_id})
                
                count += 1

        db.session.commit()
        flash(f'{count} vehicule au fost alocate cu succes.', 'success')
        return redirect(url_for('admin_page', tab='unallocated'))
    except Exception as e:
        db.session.rollback()
        flash(f"Eroare la alocarea în masă: {str(e)}", "danger")
        return redirect(url_for('admin_page', tab='unallocated'))

@app.route('/admin/company/delete/<int:id>')
def delete_company(id):
    from models import Company, Vehicle, Transaction, StockOperation
    gid = session.get('gestiune_id')
    c = Company.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    
    # 1. Detach vehicles -> Unallocated
    Vehicle.query.filter_by(company_id=id, gestiune_id=gid).update({Vehicle.company_id: None})

    # 2. Detach transactions -> Unallocated
    Transaction.query.filter_by(company_id=id, gestiune_id=gid).update({Transaction.company_id: None})

    # 3. Detach Stock Operations -> Unallocated
    StockOperation.query.filter_by(company_id=id, gestiune_id=gid).update({StockOperation.company_id: None})
    
    db.session.delete(c)
    db.session.commit()
    flash("Firma a fost ștearsă. Vehiculele și tranzacțiile au fost mutate la 'Nealocate'.", "warning")
    return redirect('/admin')

@app.route('/admin/vehicle/delete/<int:id>')
def delete_vehicle(id):
    from models import Vehicle, Transaction, StockOperation
    gid = session.get('gestiune_id')
    v = Vehicle.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    # Capture context for redirect
    comp_id = v.company_id
    
    # Check if has dependencies
    has_trans = Transaction.query.filter_by(vehicle_id=id, gestiune_id=gid).first()
    if has_trans:
        flash("Nu se poate șterge un vehicul care are tranzacții. Mutați vehiculul sau ștergeți tranzacțiile mai întâi.", "danger")
        if comp_id:
            return redirect(f'/admin?company_id={comp_id}')
        return redirect('/admin?tab=unallocated')
        
    db.session.delete(v)
    db.session.commit()
    flash("Vehiculul a fost șters.", "success")
    
    if comp_id:
        return redirect(f'/admin?company_id={comp_id}')
    return redirect('/admin?tab=unallocated')

@app.route('/admin/category/new', methods=['POST'])
def new_category():
    from models import VehicleCategory
    gid = session.get('gestiune_id')
    name = request.form.get('name')
    desc = request.form.get('description')
    if name:
        existing = VehicleCategory.query.filter_by(name=name, gestiune_id=gid).first()
        if existing:
            flash(f'Categoria "{name}" există deja în această gestiune!', 'warning')
        else:
            icon = request.form.get('icon', 'bi-tag-fill')
            vc = VehicleCategory(name=name, description=desc, icon=icon, gestiune_id=gid)
            db.session.add(vc)
            db.session.commit()
            flash(f'Categoria "{name}" a fost creată.', 'success')
    return redirect('/admin?tab=categories')

@app.route('/admin/category/edit/<int:id>', methods=['POST'])
def edit_category(id):
    from models import VehicleCategory
    gid = session.get('gestiune_id')
    c = VehicleCategory.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    name = request.form.get('name')
    desc = request.form.get('description')
    if name:
        c.name = name
        c.description = desc
        c.icon = request.form.get('icon', 'bi-tag-fill')
        db.session.commit()
        flash(f'Categoria "{name}" a fost actualizată.', 'success')
    return redirect('/admin?tab=categories')

@app.route('/admin/category/delete/<int:id>')
def delete_category(id):
    from models import VehicleCategory, Vehicle
    gid = session.get('gestiune_id')
    c = VehicleCategory.query.filter_by(id=id, gestiune_id=gid).first_or_404()
    
    # Check if used in this gestiune
    count = Vehicle.query.filter_by(category_id=id, gestiune_id=gid).count()
    if count > 0:
        flash(f'Nu se poate șterge categoria "{c.name}" deoarece are {count} utilaje alocate în acest profil.', 'danger')
    else:
        db.session.delete(c)
        db.session.commit()
        flash(f'Categoria "{c.name}" a fost ștearsă.', 'success')
    return redirect('/admin?tab=categories')

@app.route('/admin/cleanup/orphaned-transactions')
def cleanup_orphaned_transactions():
    """Find and delete transactions with NULL or invalid vehicle_id"""
    from models import Transaction, Vehicle
    gid = session.get('gestiune_id')
    
    if not gid:
        flash('Nu există nici o gestiune activă selectată!', 'danger')
        return redirect('/select-profile')
    
    # Find orphaned transactions (NULL vehicle_id or vehicle doesn't exist)
    # First: transactions with NULL vehicle_id
    null_vehicle_transactions = Transaction.query.filter_by(
        vehicle_id=None,
        gestiune_id=gid
    ).all()
    
    # Second: transactions where vehicle_id references non-existent vehicle
    all_vehicle_ids = [v.id for v in Vehicle.query.filter_by(gestiune_id=gid).all()]
    dangling_transactions = Transaction.query.filter(
        Transaction.gestiune_id == gid,
        Transaction.vehicle_id.isnot(None),
        ~Transaction.vehicle_id.in_(all_vehicle_ids)
    ).all()
    
    orphaned = null_vehicle_transactions + dangling_transactions
    count = len(orphaned)
    
    if count == 0:
        flash('Nu există tranzacții orfane în această gestiune. Baza de date este curată!', 'success')
        return redirect('/admin')
    
    # Delete orphaned transactions
    for trans in orphaned:
        db.session.delete(trans)
    
    db.session.commit()
    flash(f'Curățare completă: {count} tranzacții orfane au fost șterse din baza de date.', 'success')
    return redirect('/admin')

@app.route('/api/snapshot/save', methods=['POST'])
def save_snapshot():
    """Saves a base64 image from the browser to the local Downloads folder"""
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'success': False, 'message': 'No image data provided'}), 400
            
        # Extract base64 part
        image_data = data['image']
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]
            
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%d%m%Y_%H%M%S')
        filename = f"FuelManager_Snapshot_{timestamp}.png"
        
        # Path to Downloads folder (Windows)
        downloads_path = str(Path.home() / "Downloads")
        if not os.path.exists(downloads_path):
            # Fallback for systems where Downloads might not exist or be different
            user_profile = os.environ.get('USERPROFILE', os.path.expanduser('~'))
            downloads_path = os.path.join(user_profile, 'Downloads')
            
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path, exist_ok=True)
            
        full_path = os.path.join(downloads_path, filename)
        
        # Write file
        with open(full_path, "wb") as f:
            f.write(base64.b64decode(image_data))
            
        app.logger.info(f"Snapshot saved to: {full_path}")
        return jsonify({
            'success': True, 
            'filename': filename,
            'path': full_path
        })
    except Exception as e:
        app.logger.error(f"Error saving snapshot: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- GLOBAL ERROR HANDLER FOR EXE ---
@app.errorhandler(Exception)
def handle_exception(e):
    # Pass through HTTP errors
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
        
    # LOG THE ERROR
    logging.error(f"UNHANDLED EXCEPTION: {e}", exc_info=True)
    print(f"CRITICAL: {e}")
    
    # Return error trace to user (essential for windowed EXE debugging)
    import traceback
    trace = traceback.format_exc()
    
    return f"""
    <html>
        <body style="font-family: monospace; background: #fff0f0; padding: 20px;">
            <h1 style="color: #d32f2f;">CRITICAL SYSTEM ERROR (500)</h1>
            <p>An unexpected error occurred. Please send this screenshot to the developer.</p>
            <div style="background: #fff; border: 1px solid #ffcdd2; padding: 15px; border-radius: 5px; overflow: auto;">
                <pre>{trace}</pre>
            </div>
            <p><a href="/">Return to Home</a> | <a href="/setup">Return to Setup</a></p>
        </body>
    </html>
    """, 500

if __name__ == '__main__':
    # 1. Initialize Database & Run Migrations
    with app.app_context():
        # Migrations are already run at module level
        db.create_all()
        print(f"Database initialized at: {get_database_path()}")

    # 2. Check Single Instance
    if is_already_running(5000):
        try:
            # Native Windows message box
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, "Fuel Manager is already running!", "Fuel Manager", 0x10 | 0x40000)
        except:
            print("Fuel Manager is already running!")
        
        # Try to open existing instance
        # Try to open existing instance
        import webbrowser
        webbrowser.open('http://127.0.0.1:5000/') # Re-used import
        sys.exit(0)

    # 3. Initialize System Tray (Background)
    # This handles the "Exit" button and keeps the app "alive" visually
    from system_tray import SystemTrayManager
    tray_manager = SystemTrayManager(port=5000)
    tray_manager.run_in_background()
    print("System tray icon started (look for droplet icon in system tray)")

    # 4. Heartbeat & Auto-Shutdown Mechanism
    # (BUSY_MODE and last_heartbeat already initialized at top level)
    
    def heartbeat_monitor():
        """Checks if browser is still open. If not, shuts down server."""
        # IF RUNNING IN DESKTOP MODE (Qt), DISABLE AUTO-SHUTDOWN
        if os.environ.get('DESKTOP_MODE') == '1':
            print("Desktop Mode detected: Heartbeat monitor disabled (Window controls lifecycle).")
            return

        global last_heartbeat, BUSY_MODE
        print("Heartbeat monitor started...")
        while True:
            time.sleep(2)
            # If no heartbeat for > 20 seconds (and NOT BUSY), assume browser closed
            # Reduced to 20s per user request for faster restart
            if not BUSY_MODE and (time.time() - last_heartbeat > 20):
                print("No heartbeat received. Shutting down...")
                os.kill(os.getpid(), signal.SIGTERM)
                break
                
    # Start monitor in background
    threading.Thread(target=heartbeat_monitor, daemon=True).start()

    # 5. Launch Browser Window (App Mode)
    import subprocess
    # webbrowser already imported
    
    import webbrowser
    import subprocess
    import threading
    import sys
    import os

    def open_app_window():
        url = 'http://127.0.0.1:5000/'
        # Try Chrome first, then Edge for "App Mode" (no address bar)
        chrome_paths = [
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
        ]
        edge_path = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
        
        app_launched = False
        
        # Attempt to launch Chrome in App Mode (Maximized)
        for chrome_path in chrome_paths:
            if os.path.exists(chrome_path):
                try:
                    subprocess.Popen([chrome_path, f'--app={url}', '--start-maximized'])
                    app_launched = True
                    break
                except:
                    pass
        
        # Attempt to launch Edge in App Mode (Maximized)
        if not app_launched and os.path.exists(edge_path):
            try:
                subprocess.Popen([edge_path, f'--app={url}', '--start-maximized'])
                app_launched = True
            except:
                pass
                
        # Fallback to default browser
        if not app_launched:
            webbrowser.open(url)
        
    # Launch browser slightly after server start
    threading.Timer(1.5, open_app_window).start()
    
    # 5. Start Flask Server
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print("\n" + "=" * 60)
    print("  FUEL MANAGER v4.0 - Running")
    print("=" * 60)
    print(f"  Database: {get_database_path()}")
    print(f"  URL: http://127.0.0.1:5000/")
    print(f"  To exit: Close the console window or use the tray icon.")
    print("=" * 60 + "\n")
    
    # Production mode
    try:
        app.run(debug=False, use_reloader=False, port=5000)
    except KeyboardInterrupt:
        print("\nShutting down...")
    except SystemExit:
        print("\nShutdown requested...")
    finally:
        # Stop tray icon if running
        if tray_manager.icon:
            try:
                tray_manager.icon.stop()
            except:
                pass

