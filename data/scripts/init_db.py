"""Run once before first use: py data/scripts/init_db.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend-api" / "src"))

from usisain_backend.data import db

if __name__ == "__main__":
    db.init_db()
