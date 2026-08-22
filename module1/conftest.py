"""
pytest configuration for Module 1.
Sets PYTHONPATH so `app.*` imports work from the tests/ directory.
"""

import sys
import os

# Add the module1/ directory to the path so `from app.xxx import yyy` works
sys.path.insert(0, os.path.dirname(__file__))
