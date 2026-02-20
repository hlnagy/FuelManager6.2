
import unittest
import os
import json
import base64
from app import app, db, DATA_DIR
from models import Gestiune, Company, Transaction, Vehicle, VehicleCategory

class FuelManagerFullTest(unittest.TestCase):
    def setUp(self):
        # Use a temporary in-memory database for testing
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.client = app.test_client()
        with app.app_context():
            db.create_all()
            # Create a test profile
            self.test_gest = Gestiune(name="Test Profile", site_code="TEST")
            db.session.add(self.test_gest)
            db.session.commit()
            self.gest_id = self.test_gest.id

    def test_dashboard_access(self):
        with self.client.session_transaction() as sess:
            sess['gestiune_id'] = self.gest_id
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Fuel Manager', response.data)

    def test_company_color_logic(self):
        with app.app_context():
            c1 = Company(name="TRANSGAT-SORT", gestiune_id=self.gest_id)
            c2 = Company(name="PETROIL-IMPEX", gestiune_id=self.gest_id)
            c3 = Company(name="New Unknown Co", gestiune_id=self.gest_id)
            db.session.add_all([c1, c2, c3])
            db.session.commit()
            
            self.assertEqual(c1.color, 'primary')
            self.assertEqual(c2.color, 'success')
            # Check cyclic color
            self.assertIn(c3.color, ['orange', 'teal', 'pink', 'indigo', 'warning', 'danger', 'success', 'info', 'primary'])

    def test_snapshot_api(self):
        with self.client.session_transaction() as sess:
            sess['gestiune_id'] = self.gest_id
        
        # Fake base64 image data
        fake_image = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        
        response = self.client.post('/api/snapshot/save', 
                                    data=json.dumps({'image': fake_image}),
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Verify file exists in Downloads (or fallback path provided by API)
        saved_path = data['path']
        if os.path.exists(saved_path):
            os.remove(saved_path) # Cleanup

    def test_stock_details_page(self):
        with self.client.session_transaction() as sess:
            sess['gestiune_id'] = self.gest_id
        response = self.client.get('/admin/stock/details')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Gestionare Stoc', response.data)
        # Check if our new Snapshot button exists
        self.assertIn(b'Snapshot', response.data)

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

if __name__ == '__main__':
    unittest.main()
