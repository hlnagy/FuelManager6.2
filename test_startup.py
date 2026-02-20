
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Attempting to import app...")
try:
    from app import app, setup_restore, get_instance_path
    print("SUCCESS: app imported.")
    print(f"Instance path resolved to: {get_instance_path()}")
    print("SUCCESS: Helper functions available.")
    print("SUCCESS: setup_restore route available.")
except ImportError as e:
    print(f"FAILURE: ImportError: {e}")
    sys.exit(1)
except NameError as e:
    print(f"FAILURE: NameError (likely missing helper): {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAILURE: Runtime Exception: {e}")
    sys.exit(1)
