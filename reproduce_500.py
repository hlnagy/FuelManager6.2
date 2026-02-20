
import os
import sys
import unittest
import io

# Ensure app is in path
sys.path.append(os.getcwd())

from app import app, db

class TestSetupRestore(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()
        
        # Create a dummy sqlite file
        with open('dummy.db', 'wb') as f:
            f.write(b'SQLite format 3\x00')
            
    def tearDown(self):
        if os.path.exists('dummy.db'):
            os.remove('dummy.db')

    def test_restore_crash(self):
        print("Simulating restore request...")
        with open('dummy.db', 'rb') as f:
            data = {
                'database_file': (f, 'dummy.db')
            }
            try:
                response = self.app.post('/setup_restore', data=data, content_type='multipart/form-data', follow_redirects=True)
                print(f"Final Response Status: {response.status_code}")
                # Check for error messages in the HTML
                decoded = response.data.decode('utf-8')
                if "Restaurare eșuată" in decoded:
                    print("FAILURE: Restore failed gracefully (Flash message found).")
                    # Try to maintain context to find the specific error message
                elif "Internal Server Error" in decoded:
                    print("CAPTURED 500 in HTML body!")
                else:
                    print("SUCCESS: Redirected normally.")
            except Exception as e:
                print(f"EXCEPTION RAISED: {e}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    unittest.main()
