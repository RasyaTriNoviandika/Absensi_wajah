import sys, os

# Path project
sys.path.insert(0, os.path.dirname(__file__))

# Import Flask app
from app import app as application
