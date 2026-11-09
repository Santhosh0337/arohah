"""Lets pytest import `app` when run from the repo root or from backend/."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
