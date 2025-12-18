"""Run the Streamlit UI"""
import subprocess
import sys
from pathlib import Path

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    # Run streamlit app
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", 
        "ui/app.py",
        "--server.port=8501",
        "--server.address=localhost"
    ])

