import sys
from pathlib import Path

# Make `import app.providers...` work when pytest runs from the repo root.
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
