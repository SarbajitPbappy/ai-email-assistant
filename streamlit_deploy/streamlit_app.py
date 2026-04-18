# Streamlit Cloud entry point
# This just re-runs the actual dashboard module
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
exec(open(os.path.join(os.path.dirname(__file__), "src", "dashboard", "app.py")).read())
