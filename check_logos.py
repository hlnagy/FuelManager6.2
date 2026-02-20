import os
import sqlite3
from pathlib import Path

app_data = os.path.join(os.environ['LOCALAPPDATA'], 'FuelManager')
db_path = os.path.join(app_data, 'fuel_manager.db')

if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM company")
    companies = cursor.fetchall()
    print("Companies in DB:")
    for c in companies:
        print(f"ID: {c[0]}, Name: {c[1]}")
    
    logo_dir = os.path.join(app_data, 'logos', 'company_logos')
    if os.path.exists(logo_dir):
        print("\nLogos in company_logos folder:")
        for f in os.listdir(logo_dir):
            print(f)
    else:
        print(f"\nLogo dir not found at {logo_dir}")
    conn.close()
