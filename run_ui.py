"""Run the Streamlit UI"""
import subprocess
import sys

if __name__ == "__main__":
    # Run streamlit app
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", 
        "ui/app.py",
        "--server.port=8501",
        "--server.address=localhost"
    ])

