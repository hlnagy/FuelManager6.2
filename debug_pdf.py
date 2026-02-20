
import os
import sys
import base64
from datetime import datetime
from jinja2 import Template, Environment, FileSystemLoader

# Mock the environment
sys.path.append(os.path.abspath("."))

try:
    from services import generate_analysis_report_pdf
    print("SUCCESS: Imported generate_analysis_report_pdf")
except Exception as e:
    print(f"ERROR: Cannot import services: {e}")
    sys.exit(1)

def format_thousands(value, decimals=0):
    try:
        val = float(value)
        if decimals > 0:
            fmt = "{:,.%df}" % decimals
            return fmt.format(val).replace(",", " ").replace(".", ",")
        else:
            return "{:,}".format(int(val)).replace(",", " ")
    except:
        return value

def test_real_template():
    print("Starting REAL template PDF generation test...")
    
    # Setup Jinja environment to find templates
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['format_thousands'] = format_thousands
    
    try:
        template = env.get_template('analysis_pdf.html')
    except Exception as e:
        print(f"ERROR: Cannot load template: {e}")
        return

    # Mock Data
    mock_data = {
        'gestiune_name': "TEST GESTIUNE",
        'logo_base64': None,
        'start_date': "01.01.2024",
        'end_date': "31.01.2024",
        'generated_at': datetime.now().strftime('%d.%m.%Y %H:%M'),
        'total_fuel_budila': 12500.5,
        'total_fuel_ghid': 4500.2,
        'net_fuel': 17000.7,
        'mc_vanduti': 5000,
        'mc_sortati': 3500,
        'mc_ghid': 2000,
        'eff_vanduti': 2.5,
        'eff_sortati': 3.57,
        'eff_ghid': 2.25,
        'budila_data': [
            {'category': 'Excavator', 'fuel': 5000, 'mc_val': 2000, 'basis_name': 'Total Vanduti', 'efficiency': 2.5},
            {'category': 'Incarcator', 'fuel': 7500.5, 'mc_val': 2000, 'basis_name': 'Total Vanduti', 'efficiency': 3.75}
        ],
        'ghidfalau_data': [
            {'category': 'Buldozer', 'fuel': 4500.2, 'mc_val': 2000, 'basis_name': 'Nisip Exploatat', 'efficiency': 2.25}
        ]
    }

    try:
        html_content = template.render(**mock_data)
        print("SUCCESS: Template rendered successfully")
    except Exception as e:
        import traceback
        print(f"ERROR: Template rendering failed: {e}")
        traceback.print_exc()
        return

    # Now generate PDF
    from app import app
    with app.app_context():
        # Get a valid gestiune id for the filename
        from models import Gestiune
        gest = Gestiune.query.first()
        gid = gest.id if gest else 1
        
        filepath, msg = generate_analysis_report_pdf(html_content, gid)
        
        if filepath:
            print(f"SUCCESS: PDF generated at {filepath}")
        else:
            print(f"FAILURE: {msg}")

if __name__ == "__main__":
    test_real_template()
