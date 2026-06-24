# tests/conftest.py
import sys
import os

# Add project root to Python path so pytest can find 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))