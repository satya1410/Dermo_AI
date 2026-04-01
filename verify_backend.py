
import sys
import os

sys.path.append(os.getcwd())

try:
    from backend.app import api
    print("Backend API imported successfully.")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
