import pandas as pd
from models import db, Transaction, Company, Vehicle
from datetime import datetime
import os
from pathlib import Path


# Hardcoded rules for company assignment
def get_company_for_plate(plate, gestiune_id):
    # Logic moved to database lookups only
    return None

def process_csv_import(file_path, gestiune_id):
    try:
        # The specific CSV format has no proper header and uses latin-1 encoding.
        # Try default separator (comma) first
        df = pd.read_csv(file_path, header=None, encoding='latin-1')
        
        # If only 1 column detected, try semicolon (common in EU CSVs)
        if len(df.columns) < 2:
             df = pd.read_csv(file_path, header=None, encoding='latin-1', sep=';')
        imported_count = 0
        skipped_count = 0
        duplicates_list = []  # List for potential review/approval
        
        
        # Use configured log directory from app config if possible, or relative
        import os
        log_dir = os.path.join(os.environ.get('LOCALAPPDATA', '.'), 'FuelManager', 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = os.path.join(log_dir, f'import_debug_{timestamp}.log')
                 
        try:
            log_file = open(log_filename, 'w', encoding='utf-8')
        except Exception as e:
            print(f"WARNING: Could not create log file {log_filename}: {e}")
            # Fallback to devnull-like behavior
            log_file = open(os.devnull, 'w')

        try:
            log_file.write(f"Starting import at {timestamp}\n")
            
            for index, row in df.iterrows():
                try:
                    # Basic validation: Check if row has enough columns

                    # Basic validation: Check if row has enough columns
                    # RELAXED validation: maybe some rows are shorter but have data we need?
                    if len(row) < 14: # Reduced from 16
                         log_file.write(f"Row {index}: Skipped - Too short ({len(row)})\n")
                         print(f"DEBUG: Row {index} too short: {len(row)}")
                         continue
                    
                    # --- DYNAMIC COLUMN DETECTION ---
                    # The CSV structure shifts for some rows (machines/transports).
                    # Standard structure (based on prev success): 
                    # Row[10]=Date, Row[11]=Time, Row[14]=Qty, Row[15]=Plate
                    
                    # Shifted structure (based on user example):
                    # 0=..., 10=Date(04.02.2026), 11=Time(10:38), 12=Unit(1), 13=(Empty), 14=Odometer(0), 15=Plate(EX.KOM002), 16=Qty(26005 -> 260.05?)
                    
                    # Let's verify where the Plate is.
                    # Usually Plate is in col 15.
                    plate_col_15 = str(row[15]).strip().upper()
                    
                    # Initial assumptions
                    date_val = str(row[10]).strip()
                    time_val = str(row[11]).strip()
                    
                    # Determine Plate and Qty based on structure
                    plate = ""
                    qty_raw = ""
                    qty = 0.0
                    
                    # CASE 1: Standard (Plate in 15, Qty in 14) -> Used for most cars
                    # CASE 2: Shifted (Plate in 15, Qty in 16?? No, user said 26005 is quantity 260.05)
                    
                    # Let's look at the data from the user example:
                    # Row[15] = "EX.KOM002"
                    # Row[16] = 26005 (This looks like quantity without decimal point!)
                    
                    # So if Plate is in 15, Qty might be in 14 or 16.
                    
                    # Check col 15 for Plate
                    # Relaxed validation: Just check length. Allow spaces!
                    if len(plate_col_15) > 1 and plate_col_15 != 'NAN':
                        plate = plate_col_15
                        
                        # Now find Qty.
                        # Check col 14 first (Standard)
                        val_14 = 0.0
                        try:
                            val_14 = float(str(row[14]).replace(',', '.'))
                        except:
                            val_14 = 0.0
                            
                        # Check col 16 (Shifted?)
                        val_16 = 0.0
                        try:
                            if len(row) > 16:
                                raw_16 = str(row[16]).replace(',', '.')
                                try:
                                    val_16 = float(raw_16)
                                except:
                                    pass
                        except:
                            val_16 = 0.0
                            
                        # DECISION LOGIC
                        # Prefer Col 14 if reasonable (>0 and <1000 usually, but big trucks can take 1000?). 
                        # But if Col 16 exists and looks like the "Shifted" pattern (huge integer), prioritize that?
                        
                        # Issue: If Col 14 is "0" (Odometer) and Col 16 is "26005" (Qty), we want Col 16.
                        # If Col 14 is "50.0" (Qty) and Col 16 is "1" (Something else?), we want Col 14.
                        
                        qty = 0.0
                        
                        # CSV format: the last 2 digits are ALWAYS decimals.
                        # So 801 -> 8.01, 4003 -> 40.03, 15012 -> 150.12
                        # ALL col_16 values must be divided by 100.
                        
                        if val_16 > 0:
                             qty = val_16 / 100.0
                             log_file.write(f"Row {index}: Selected Shifted Qty from Col 16 ({val_16} -> {qty})\n")
                        elif val_14 > 0:
                             qty = val_14
                             # log_file.write(f"Row {index}: Selected Standard Qty from Col 14 ({qty})\n")
                        else:
                             # Try Col 13 as last resort
                             try:
                                val_13 = float(str(row[13]).replace(',', '.'))
                                if val_13 > 0:
                                    qty = val_13
                                    log_file.write(f"Row {index}: Selected Fallback Qty from Col 13 ({qty})\n")
                             except:
                                 pass
                    
                    else:
                        # Plate validation failed (too short or NAN)
                         log_file.write(f"Row {index}: Skipped - Plate '{plate_col_15}' invalid.\n")
                         continue
                         
                    if date_val.lower() == 'date' or not date_val: 
                        continue
                        
                    # Parse DateTime
                    # Parse DateTime
                    # Relaxed: If time is missing or invalid, default to 00:00
                    if not time_val or len(time_val) < 3:
                        time_val = "00:00"
                        
                    date_str = f"{date_val} {time_val}"
                    dt = None
                    try:
                        # Try standard format
                        dt = datetime.strptime(date_str, '%d.%m.%Y %H:%M')
                    except ValueError:
                        # Try without time if fallback needed (though we added 00:00)
                        try:
                            dt = datetime.strptime(date_str, '%d.%m.%Y')
                        except ValueError:
                             log_file.write(f"Row {index}: Skipped - Invalid Date '{date_str}'\n")
                             continue
                    
                    if qty <= 0:
                         log_file.write(f"Row {index}: Skipped - Qty invalid ({qty}). Raw14={row[14]}\n")
                         continue


                    # Find or Create Vehicle
                    vehicle = Vehicle.query.filter_by(plate_number=plate, gestiune_id=gestiune_id).first()
                    company = get_company_for_plate(plate, gestiune_id)
                    
                    trans_company = None
                    if company:
                        trans_company = company
                    elif vehicle and vehicle.company:
                        # If a vehicle belongs to TRANSGAT-SORT but has no category, 
                        # it was likely auto-created by the old fallback. Treat as unallocated.
                        if vehicle.company.name.upper() == 'TRANSGAT-SORT' and not vehicle.category_id:
                            trans_company = None
                        else:
                            trans_company = vehicle.company
                    else:
                        trans_company = None

                    if not vehicle:
                        vehicle = Vehicle(plate_number=plate, company=company, gestiune_id=gestiune_id)
                        db.session.add(vehicle)
                        db.session.commit()
                    else:
                        if not vehicle.company_id and company:
                            vehicle.company = company

                    # Check for Duplicate
                    exists = Transaction.query.filter_by(
                        date=dt, 
                        vehicle_id=vehicle.id, 
                        quantity=qty,
                        gestiune_id=gestiune_id
                    ).first()
                    
                    if not exists:
                        new_trans = Transaction(
                            date=dt,
                            vehicle_id=vehicle.id,
                            company_id=trans_company.id if trans_company else None,
                            quantity=qty,
                            gestiune_id=gestiune_id
                        )
                        db.session.add(new_trans)
                        imported_count += 1
                        log_file.write(f"Row {index}: Imported {plate} {qty}L\n")
                    else:
                        skipped_count += 1
                        # Add to duplicates list for potential review/approval
                        duplicates_list.append({
                            'row_index': index,
                            'date': dt.strftime('%Y-%m-%d'),
                            'time': dt.strftime('%H:%M'),
                            'plate': plate,
                            'quantity': qty,
                            'company': trans_company.name if trans_company else 'N/A',
                            'company_id': trans_company.id if trans_company else None,
                            'existing_id': exists.id,
                            'gestiune_id': gestiune_id
                        })
                        log_file.write(f"Row {index}: Skipped - Duplicate\n")
                        
                except Exception as e:
                    # log_file.write(f"Row {index}: Error - {e}\n")
                    # Log full row on error
                    log_file.write(f"Row {index}: CRITICAL ERROR {e} \nContent: {str(row.values)}\n")
                    continue
                
            # Log rows that didn't even make it into the loop or were skipped early (if we wanted to track headers)
            # But let's just track the ones we explicitly skip in the loop.

                
            db.session.commit()
            return True, f"Imported {imported_count} records. Found {len(duplicates_list)} duplicates.", imported_count, duplicates_list
        
        except Exception as e:
            return False, f"Critical error in loop: {str(e)}", 0, []
        finally:
            if 'log_file' in locals() and hasattr(log_file, 'close'):
                 try:
                     log_file.close()
                 except:
                     pass

    except Exception as e:
        return False, f"Global error: {str(e)}", 0, []

def generate_pdf_report(start_date, end_date, gestiune_id, company_id=None, bon_number=""):
    from fpdf import FPDF
    import os
    import sys

    # Parse inputs (expecting 'YYYY-MM-DDTHH:MM' from datetime-local input)
    # If they come as strings, convert.
    if isinstance(start_date, str):
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
        except ValueError:
                # Fallback to date only if time is missing
                start_date = datetime.strptime(start_date, '%Y-%m-%d')

    if isinstance(end_date, str):
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
        except ValueError:
            # Fallback to end of day if only date provided
            end_date = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)

    # Base query
    query = Transaction.query.filter(
        Transaction.gestiune_id == gestiune_id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    )
    
    # Optional company filter
    if company_id:
        query = query.filter(Transaction.company_id == company_id)
        
    # Group by company first, then date
    transactions = query.order_by(Transaction.company_id, Transaction.date).all()

    if not transactions:
        return None, "Nu s-au găsit tranzacții în perioada selectată."
        
    def clean_to_ascii(text):
        """Replaces Romanian diacritics with ASCII equivalents to prevent PDF errors."""
        if text is None:
            return ""
        if not isinstance(text, str):
            return str(text)
        
        replacements = {
            'ă': 'a', 'Ă': 'A',
            'â': 'a', 'Â': 'A',
            'î': 'i', 'Î': 'I',
            'ș': 's', 'Ș': 'S',
            'ț': 't', 'Ț': 'T',
            '–': '-', '”': '"', '„': '"'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        
        # Fallback for anything else
        try:
            return text.encode('latin-1', 'replace').decode('latin-1')
        except:
            return text

    class PDF(FPDF):
        def header(self):
            pass

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Layout configuration
    SLIPS_PER_PAGE = 2
    
    # Resolve Series Globaly to handle collisions
    # 1. Fetch all companies to build the series map
    from models import Company
    all_companies = Company.query.order_by(Company.id).all()
    series_map = {}
    taken_series = set()

    for c in all_companies:
        c_name = c.name if c.name else "UNKNOWN"
        if len(c_name) < 3:
            s = c_name.upper().ljust(3, 'X')
        else:
            # Potential candidates generator
            candidates = []
            
            # Option A: Standard (1st + 2nd + Last)
            s_std = f"{c_name[0]}{c_name[1]}{c_name[-1]}".upper()
            candidates.append(s_std)
            
            # Option B: Word initials
            import re
            words = re.split(r'[\s\-]+', c_name)
            if len(words) > 1:
                for w in words[1:]:
                    if w:
                        s_word = f"{c_name[0]}{w[0]}{c_name[-1]}".upper()
                        if s_word not in candidates:
                            candidates.append(s_word)

            # Option C: Sequential scan
            for i in range(2, len(c_name) - 1):
                s_scan = f"{c_name[0]}{c_name[i]}{c_name[-1]}".upper()
                if s_scan not in candidates:
                    candidates.append(s_scan)

            # Assign first available
            assigned = None
            for cand in candidates:
                if cand not in taken_series:
                    assigned = cand
                    break
            
            # Fallback
            if not assigned:
                assigned = f"{c_name[0]}X{c_name[-1]}".upper() 

            series_map[c.id] = assigned
            taken_series.add(assigned)

    count = 0
    
    # Per-company counter state
    last_company_id = None
    anexa_counter = 1
    
    for t in transactions:
        # Check for company change to reset counter
        if last_company_id != t.company_id:
            anexa_counter = 1
            last_company_id = t.company_id
        else:
            anexa_counter += 1
            
        if count % SLIPS_PER_PAGE == 0:
            pdf.add_page()
            y_start = 10
        else:
            # Second slip starts at 148mm (approx half page)
            y_start = 150
            
        # Draw Separator Line if it's the second slip
        if count % SLIPS_PER_PAGE == 1:
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, 140, 200, 140)
            pdf.set_draw_color(0, 0, 0) # Reset
            
    # --- Content Generation ---
        # Get Series for current company
        series = series_map.get(t.company_id, "---")

        company_name = clean_to_ascii(t.company.name if t.company else "NECUNOSCUT")
        cui = clean_to_ascii(t.company.cui if t.company and t.company.cui else "-")
        address = clean_to_ascii(t.company.address if t.company and t.company.address else "-")
        
        # Use our managed counter
        anexa_nr = f"{anexa_counter:03d}" 
        
        pdf.set_y(y_start)
        
        # --- Header Section ---
        # Left Side: Company Details
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(100, 6, company_name, 0, 1, 'L')
        
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(100, 5, f"CUI: {cui}", 0, 1, 'L')
        pdf.cell(100, 5, f"Adresa: {address}", 0, 1, 'L')
        
        # Right Side: Date, Series, Number
        pdf.set_y(y_start)
        pdf.set_x(110)
        
        pdf.set_font('Helvetica', '', 10)
        # Date
        pdf.cell(80, 6, f"Data: {t.date.strftime('%d.%m.%Y')}", 0, 1, 'R')
        
        pdf.set_x(110)
        seria_txt = clean_to_ascii(f"Seria {series}  |  Număr Anexă: {anexa_nr}")
        pdf.cell(80, 6, seria_txt, 0, 1, 'R')
        
        if bon_number:
            pdf.set_x(110)
            bonus_txt = clean_to_ascii(f"Atașat la Bon Consum: {bon_number}")
            pdf.cell(80, 6, bonus_txt, 0, 1, 'R')

        pdf.ln(10)
        
        # Title of the Ticket
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, clean_to_ascii("BON DE ALIMENTARE COMBUSTIBIL"), 0, 1, 'C')
        pdf.ln(5)
        
        # --- Transaction Data (Table) ---
        pdf.set_font('Helvetica', '', 10)
        
        col_w = [35, 60, 45, 15, 35] 
        col_h = [clean_to_ascii("Data"), clean_to_ascii("Vehicul"), clean_to_ascii("Produs"), "U.M.", clean_to_ascii("Cantitate")]
        
        # Header Row
        pdf.set_x(10) # Margin
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font('Helvetica', 'B', 10)
        
        for i in range(5):
            pdf.cell(col_w[i], 8, col_h[i], 1, 0, 'C', fill=True)
        pdf.ln()
        
        # Data Row
        pdf.set_x(10)
        pdf.set_font('Helvetica', '', 10)
        
        # Clean data
        row_data = [
            t.date.strftime('%d.%m.%Y'),
            clean_to_ascii(t.vehicle.plate_number if t.vehicle else "NECUNOSCUT"),
            clean_to_ascii("Motorina"), 
            "L",
            f"{t.quantity:.2f}"
            ]
            
        pdf.cell(col_w[0], 8, row_data[0], 1, 0, 'C')
        pdf.cell(col_w[1], 8, row_data[1], 1, 0, 'C')
        pdf.cell(col_w[2], 8, row_data[2], 1, 0, 'C')
        pdf.cell(col_w[3], 8, row_data[3], 1, 0, 'C')
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(col_w[4], 8, row_data[4], 1, 1, 'C')
        
        # Signatures
        pdf.ln(15)
        
        y_sig = pdf.get_y()
        pdf.set_x(20)
        pdf.cell(60, 5, clean_to_ascii("Semnătură Șofer:"), 0, 0, 'C')
        pdf.cell(60, 5, clean_to_ascii("Semnătură Gestionar:"), 0, 0, 'C')
        
        pdf.set_y(y_sig + 10)
        pdf.set_x(20)
        pdf.cell(60, 5, "..........................", 0, 0, 'C')
        pdf.cell(60, 5, "..........................", 0, 0, 'C')
        
        
        # Footer of slip
        pdf.ln(5)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 5, 'Pret unitar: 0.00 RON | Valoare: 0.00 RON', 0, 1, 'L')
        
        count += 1

    # Save
    
    from models import Gestiune
    gest = Gestiune.query.get(gestiune_id)
    gest_name = gest.name.replace(" ", "_") if gest else "Gestiune"

    # PDF System v6.1: Save to Downloads
    downloads_path = Path.home() / "Downloads"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    
    filename = f"{timestamp}_Bonuri_{gest_name}.pdf"
    if company_id:
            filename = f"{timestamp}_Bonuri_{gest_name}_company_{company_id}.pdf"
            
    filepath = str(downloads_path / filename)
    
    pdf.output(filepath)
    
    return filepath, f"Generat {len(transactions)} bonuri."

class HistoryService:
    @staticmethod
    def log_action(table_name, record_id, action_type, data_obj, pre_update_state=None, gestiune_id=None):
        """
        Log an action for UNDO/REDO functionality.
        
        Args:
            table_name: Name of the database table
            record_id: ID of the affected record
            action_type: 'CREATE', 'UPDATE', or 'DELETE'
            data_obj: The SQLAlchemy object (post-state for UPDATE/CREATE, pre-state for DELETE)
            pre_update_state: For UPDATE actions, pass the state BEFORE update
        """
        from models import HistoryLog
        import json
        
        # When a new action occurs, clear ALL previously undone logs
        # This prevents conflicts in redo stack
        HistoryLog.query.filter_by(is_undone=True).delete()
        
        # Serialize data (avoiding relationships)
        snapshot = {}
        if data_obj:
            for col in data_obj.__table__.columns:
                val = getattr(data_obj, col.name)
                # Handle datetime
                if isinstance(val, datetime):
                    val = val.isoformat()
                snapshot[col.name] = val
        
        # For UPDATE, store BOTH pre and post state
        pre_snapshot = None
        if action_type == 'UPDATE' and pre_update_state:
            pre_snapshot = {}
            for col in pre_update_state.__table__.columns:
                val = getattr(pre_update_state, col.name)
                if isinstance(val, datetime):
                    val = val.isoformat()
                pre_snapshot[col.name] = val
                
        log = HistoryLog(
            table_name=table_name,
            record_id=record_id,
            action_type=action_type,
            data_snapshot=json.dumps(snapshot),
            pre_update_snapshot=json.dumps(pre_snapshot) if pre_snapshot else None,
            is_undone=False,
            gestiune_id=gestiune_id
        )
        db.session.add(log)
        db.session.commit()

    @staticmethod
    def undo(gestiune_id):
        """
        Undo the last action in the history for a specific gestiune.
        """
        from models import HistoryLog, StockOperation, Transaction
        import json
        
        # Find last active log FOR THIS GESTIUNE
        last_log = HistoryLog.query.filter_by(is_undone=False, gestiune_id=gestiune_id).order_by(HistoryLog.id.desc()).first()
        
        if not last_log:
            return False, "Nu există acțiuni de anulat."
            
        try:
            model_cls = StockOperation if last_log.table_name == 'StockOperation' else Transaction
            data = json.loads(last_log.data_snapshot) if last_log.data_snapshot else {}
            record_id = last_log.record_id
            
            if last_log.action_type == 'CREATE':
                # Inverse of CREATE: Delete the record
                obj = model_cls.query.filter_by(id=record_id, gestiune_id=gestiune_id).first()
                if obj:
                    db.session.delete(obj)
                else:
                    return False, "Obiectul nu mai există pentru a fi șters sau aparține altei gestiuni."
                    
            elif last_log.action_type == 'UPDATE':
                # Inverse of UPDATE: Restore to pre-update state
                obj = model_cls.query.filter_by(id=record_id, gestiune_id=gestiune_id).first()
                if not obj:
                    return False, "Obiectul nu mai există pentru a fi restaurat sau aparține altei gestiuni."
                
                # Use pre_update_snapshot if available, otherwise use data_snapshot (legacy)
                restore_data = json.loads(last_log.pre_update_snapshot) if last_log.pre_update_snapshot else data
                
                for k, v in restore_data.items():
                    # Skip relational fields and IDs
                    if k in ['id', 'company', 'vehicle']:
                        continue
                    # Convert datetime strings back
                    if k == 'date' and v:
                        v = datetime.fromisoformat(v)
                    setattr(obj, k, v)
                        
            elif last_log.action_type == 'DELETE':
                # Inverse of DELETE: Re-create the object
                # We DON'T force the original ID (causes conflicts)
                # Instead we create a new record and update the log to track new ID
                
                # Remove problematic fields
                restore_data = {k: v for k, v in data.items() if k not in ['company', 'vehicle']}
                
                # Convert date string back to datetime
                if 'date' in restore_data and restore_data['date']:
                    restore_data['date'] = datetime.fromisoformat(restore_data['date'])
                
                # Remove the ID to let database auto-assign (prevents conflicts)
                original_id = restore_data.pop('id', None)
                
                obj = model_cls(**restore_data)
                db.session.add(obj)
                db.session.flush()  # Get new ID
                
                # Update log to track new ID for potential redo
                last_log.record_id = obj.id
                
            # Mark as undone
            last_log.is_undone = True
            db.session.commit()
            return True, f"Anulare reușită: {last_log.action_type} pentru {last_log.table_name}."
            
        except Exception as e:
            db.session.rollback()
            return False, f"Eroare la anulare: {str(e)}"

    @staticmethod
    def redo(gestiune_id):
        """
        Redo the most recently undone action for a specific gestiune.
        """
        from models import HistoryLog, StockOperation, Transaction
        import json
        
        # Find most recent undone log FOR THIS GESTIUNE
        retry_log = HistoryLog.query.filter_by(is_undone=True, gestiune_id=gestiune_id).order_by(HistoryLog.id.desc()).first()
        
        if not retry_log:
            return False, "Nu există acțiuni de refăcut."
              
        try:
            model_cls = StockOperation if retry_log.table_name == 'StockOperation' else Transaction
            data = json.loads(retry_log.data_snapshot) if retry_log.data_snapshot else {}
            record_id = retry_log.record_id
            
            if retry_log.action_type == 'CREATE':
                # Redo CREATE: Re-create the object (it was deleted by undo)
                restore_data = {k: v for k, v in data.items() if k not in ['company', 'vehicle']}
                
                if 'date' in restore_data and restore_data['date']:
                    restore_data['date'] = datetime.fromisoformat(restore_data['date'])
                
                # Remove ID to avoid conflicts
                restore_data.pop('id', None)
                
                obj = model_cls(**restore_data)
                db.session.add(obj)
                db.session.flush()
                
            elif retry_log.action_type == 'DELETE':
                # Redo DELETE: Delete the re-created object
                obj = model_cls.query.filter_by(id=record_id, gestiune_id=gestiune_id).first()
                if obj:
                    db.session.delete(obj)
                else:
                    return False, "Obiectul nu mai există pentru a fi șters sau aparține altei gestiuni."
                     
            elif retry_log.action_type == 'UPDATE':
                # Redo UPDATE: Restore to post-update state
                obj = model_cls.query.filter_by(id=record_id, gestiune_id=gestiune_id).first()
                if not obj:
                    return False, "Obiectul nu mai există pentru a fi actualizat sau aparține altei gestiuni."
                
                # Use the main data_snapshot for post-update state
                for k, v in data.items():
                    if k in ['id', 'company', 'vehicle']:
                        continue
                    if k == 'date' and v:
                        v = datetime.fromisoformat(v)
                    setattr(obj, k, v)

            # Mark as no longer undone
            retry_log.is_undone = False
            db.session.commit()
            return True, f"Refacere reușită: {retry_log.action_type} pentru {retry_log.table_name}."
            
        except Exception as e:
            db.session.rollback()
            return False, f"Eroare la refacere: {str(e)}"


def generate_monthly_report_pdf(start_date, end_date, gestiune_id, initial_series=None, final_series=None):
    """
    Generate comprehensive monthly fuel report with:
    1. Summary statistics (per company and overall)
    2. Chronological transaction listing (all companies)
    """
    import sys
    import traceback
    
    from fpdf import FPDF
    from models import Company, StockOperation, Transaction, Gestiune
    from extensions import db
    from sqlalchemy import func
    import os
    from datetime import datetime
    
    # Helper function for ASCII conversion
    def clean_to_ascii(text):
        if text is None:
            return ""
        if not isinstance(text, str):
            return str(text)
        
        replacements = {
            'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
            'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T',
            '–': '-', '”': '"', '„': '"'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        
        # Fallback for anything else
        try:
            return text.encode('latin-1', 'replace').decode('latin-1')
        except:
            return text
    
    # Parse date inputs
    if isinstance(start_date, str):
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
        except ValueError:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
    
    if isinstance(end_date, str):
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
        except ValueError:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    
    # Get all companies for this gestiune
    companies = Company.query.filter_by(gestiune_id=gestiune_id).order_by(Company.id).all()
    
    # Calculate statistics per company
    company_stats = []
    total_in_general = 0
    total_out_general = 0
    total_initial_stock = 0
    total_final_stock = 0
    
    for c in companies:
        # Stoc Initial = only INITIAL entries (snapshot at start of month)
        stock_initial = db.session.query(func.sum(StockOperation.quantity)).filter(
            StockOperation.gestiune_id == gestiune_id,
            StockOperation.company_id == c.id,
            StockOperation.operation_type == 'INITIAL'
        ).scalar() or 0
        
        # IN during period
        in_period = db.session.query(func.sum(StockOperation.quantity)).filter(
            StockOperation.gestiune_id == gestiune_id,
            StockOperation.company_id == c.id,
            StockOperation.operation_type == 'IN',
            StockOperation.date >= start_date,
            StockOperation.date <= end_date
        ).scalar() or 0
        
        # Total Iesit = consumption + manual OUT during period
        out_manual = db.session.query(func.sum(StockOperation.quantity)).filter(
            StockOperation.gestiune_id == gestiune_id,
            StockOperation.company_id == c.id,
            StockOperation.operation_type == 'OUT',
            StockOperation.date >= start_date,
            StockOperation.date <= end_date
        ).scalar() or 0
        
        consumed_period = db.session.query(func.sum(Transaction.quantity)).filter(
            Transaction.gestiune_id == gestiune_id,
            Transaction.company_id == c.id,
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).scalar() or 0
        
        out_period = out_manual + consumed_period
        
        stock_final = stock_initial + in_period - out_period
        
        company_stats.append({
            'name': clean_to_ascii(c.name),
            'stock_initial': stock_initial,
            'total_in': in_period,
            'total_out': out_period,
            'stock_final': stock_final
        })
        
        total_in_general += in_period
        total_out_general += out_period
        total_initial_stock += stock_initial
        total_final_stock += stock_final
    
    from fpdf import FPDF
    
    # Istoric Cronologic: ONLY consumption transactions
    all_transactions = db.session.query(Transaction).filter(
        Transaction.gestiune_id == gestiune_id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).order_by(Transaction.date).all()
    
    # Build chronological list from transactions only
    combined = []
    for trans in all_transactions:
        vehicle = trans.vehicle.plate_number if trans.vehicle else 'N/A'
        comp_name = 'N/A'
        if trans.company_id:
            comp = Company.query.filter_by(id=trans.company_id, gestiune_id=gestiune_id).first()
            if comp: comp_name = comp.name
            
        combined.append({
            'date': trans.date,
            'type': 'CONSUM',
            'vehicle': vehicle,
            'quantity': trans.quantity,
            'company': comp_name
        })
    
    combined.sort(key=lambda x: x['date'])
    
    class PDF(FPDF):
       def header(self):
           pass
       def footer(self):
           self.set_y(-15)
           self.set_font('Helvetica', 'I', 8)
           self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

    # Generate PDF
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    
    # Title
    pdf.cell(0, 10, clean_to_ascii('Raport Lunar - Gestiune Motorina'), 0, 1, 'C')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"Perioada: {start_date.strftime('%d.%m.%Y %H:%M')} - {end_date.strftime('%d.%m.%Y %H:%M')}", 0, 1, 'C')
    pdf.ln(5)
    
    # Summary Table
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, clean_to_ascii('Sumar Statistic'), 0, 1, 'L')
    pdf.set_font('Helvetica', 'B', 8)
    
    # Table header
    pdf.cell(60, 6, 'Firma', 1, 0, 'C')
    pdf.cell(30, 6, 'Stoc Initial', 1, 0, 'C')
    pdf.cell(30, 6, 'Total Intrat', 1, 0, 'C')
    pdf.cell(30, 6, 'Total Iesit', 1, 0, 'C')
    pdf.cell(30, 6, 'Stoc Final', 1, 1, 'C')
    
    pdf.set_font('Helvetica', '', 8)
    for stat in company_stats:
        pdf.cell(60, 6, stat['name'], 1, 0, 'L')
        pdf.cell(30, 6, f"{stat['stock_initial']:.2f} L", 1, 0, 'R')
        pdf.cell(30, 6, f"{stat['total_in']:.2f} L", 1, 0, 'R')
        pdf.cell(30, 6, f"{stat['total_out']:.2f} L", 1, 0, 'R')
        pdf.cell(30, 6, f"{stat['stock_final']:.2f} L", 1, 1, 'R')
    
    # Overall totals
    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(60, 6, 'TOTAL GENERAL', 1, 0, 'L')
    # pdf.cell(30, 6, f"{total_initial_stock:.2f} L", 1, 0, 'R') # Removed to fit
    pdf.cell(30, 6, f"{total_in_general:.2f} L", 1, 0, 'R')
    pdf.cell(60, 6, f"{total_out_general:.2f} L", 1, 0, 'R')
    # pdf.cell(30, 6, f"{total_final_stock:.2f} L", 1, 1, 'R')
    pdf.ln(10)

    # PUMP SERIES SECTION
    if initial_series is not None and final_series is not None:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 8, clean_to_ascii('Verificare Contoare Pompa'), 0, 1, 'L')
        pdf.set_font('Helvetica', '', 9)
        
        series_diff = final_series - initial_series
        
        # Simple grid
        pdf.cell(50, 6, 'Serie Initiala:', 0, 0, 'L')
        pdf.cell(40, 6, f"{initial_series:.2f}", 0, 1, 'L')
        
        pdf.cell(50, 6, 'Serie Finala:', 0, 0, 'L')
        pdf.cell(40, 6, f"{final_series:.2f}", 0, 1, 'L')
        
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(50, 6, 'Diferenta Serii:', 0, 0, 'L')
        pdf.cell(40, 6, f"{series_diff:.2f} L", 0, 1, 'L')
        
        pdf.cell(50, 6, 'Total Iesit (Calculat):', 0, 0, 'L')
        pdf.cell(40, 6, f"{total_out_general:.2f} L", 0, 1, 'L')
        
        # Match Check
        match_diff = abs(series_diff - total_out_general)
        if match_diff < 1.0: # Tolerance of 1 liter
            pdf.set_text_color(0, 128, 0)
            pdf.cell(0, 6, clean_to_ascii(f"OK (Diferenta: {match_diff:.2f} L)"), 0, 1, 'L')
        else:
            pdf.set_text_color(255, 0, 0)
            pdf.cell(0, 6, clean_to_ascii(f"DISCREPANTA (Diferenta: {match_diff:.2f} L)"), 0, 1, 'L')
        
        pdf.set_text_color(0, 0, 0) # Reset
        pdf.ln(5)

    pdf.ln(5)
    
    # Detailed Transactions
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, clean_to_ascii('Istoric Cronologic'), 0, 1, 'L')
    pdf.set_font('Helvetica', 'B', 8)
    
    # Table header
    pdf.cell(35, 6, 'Data/Ora', 1, 0, 'C')
    pdf.cell(50, 6, 'Firma', 1, 0, 'C')
    pdf.cell(25, 6, 'Tip', 1, 0, 'C')
    pdf.cell(50, 6, 'Vehicul/Detalii', 1, 0, 'C')
    pdf.cell(30, 6, 'Cantitate', 1, 1, 'C')
    
    pdf.set_font('Helvetica', '', 7)
    for item in combined:
        pdf.cell(35, 5, item['date'].strftime('%d.%m.%Y %H:%M'), 1, 0, 'L')
        pdf.cell(50, 5, clean_to_ascii(item['company'][:20]), 1, 0, 'L')
        pdf.cell(25, 5, item['type'], 1, 0, 'C')
        pdf.cell(50, 5, clean_to_ascii(item['vehicle'][:25]), 1, 0, 'L')
        pdf.cell(30, 5, f"{item['quantity']:.2f} L", 1, 1, 'R')
    
    # Save PDF
    # PDF System v6.1: Save to Downloads
    downloads_path = Path.home() / "Downloads"
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    
    gest_name = f"Gestiune_{gestiune_id}"
    gest = Gestiune.query.get(gestiune_id)
    if gest: gest_name = gest.name.replace(" ", "_")
        
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    filename = f"Raport_Lunar_{gest_name}_{start_str}_{end_str}.pdf"
    filepath = str(downloads_path / filename)
    
    pdf.output(filepath)
    
    return filepath, "PDF generat cu succes"


def generate_analysis_report_pdf(html_content, gestiune_id):
    """
    Generate professional analysis report using xhtml2pdf.
    """
    try:
        from xhtml2pdf import pisa
    except (ImportError, OSError):
        import sys
        from unittest.mock import MagicMock
        # Mock Cairo-related modules to bypass library checks on Windows
        mock = MagicMock()
        sys.modules["cairocffi"] = mock
        sys.modules["cairo"] = mock
        sys.modules["rlpycairo"] = mock
        from xhtml2pdf import pisa
    import os
    import sys
    import base64
    from datetime import datetime
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    def link_callback(uri, rel):
        """
        Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
        """
        import os
        # If absolute path or starts with file://, resolve it correctly
        if uri.startswith('file://'):
            return uri.replace('file://', '')
        if os.path.isabs(uri):
            return uri
        return uri

    
    # v6.2 Desktop Rebuild: Target Downloads folder
    downloads_path = Path.home() / "Downloads"

    # 1. Base64 Logo support (By-pass path issues)
    def get_base64_image(image_path):
        if image_path and os.path.exists(image_path):
            try:
                with open(image_path, "rb") as img_file:
                    ext = os.path.splitext(image_path)[1][1:]
                    return f"data:image/{ext};base64,{base64.b64encode(img_file.read()).decode()}"
            except: return None
        return None

    from models import Gestiune
    gest = Gestiune.query.get(gestiune_id)
    gest_name = gest.name.replace(" ", "_") if gest else "Gestiune"
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"{timestamp}_Analiza_{gest_name}.pdf"
    filepath = str(downloads_path / filename)

    with open(filepath, "wb") as f:
        pisa_status = pisa.CreatePDF(
            html_content, 
            dest=f, 
            encoding='utf-8',
            link_callback=link_callback
        )

    if pisa_status.err:
        return None, "A apărut o eroare la generarea PDF-ului."
    
    return filepath, "PDF generat cu succes"
