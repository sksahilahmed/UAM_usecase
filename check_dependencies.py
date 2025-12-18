"""Check and install missing dependencies"""
import sys
import subprocess

REQUIRED_PACKAGES = [
    "openpyxl>=3.1.2",
    "pandas>=2.1.0",
    "python-dotenv>=1.0.0",
    "sqlalchemy>=2.0.0",
    "pydantic>=2.5.0",
    "openai>=1.3.0",
    "langchain>=0.1.0",
    "langchain-openai>=0.0.2",
    "loguru>=0.7.2",
    "crewai>=0.1.0",
    "streamlit>=1.28.0",
    "plotly>=5.17.0",
]

def check_package(package_name):
    """Check if a package is installed"""
    package = package_name.split(">=")[0].split("==")[0]
    try:
        __import__(package.replace("-", "_"))
        return True
    except ImportError:
        return False

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    """Check and install missing dependencies"""
    print("="*70)
    print("  Checking Dependencies")
    print("="*70 + "\n")
    
    missing = []
    installed = []
    
    for package in REQUIRED_PACKAGES:
        package_name = package.split(">=")[0].split("==")[0]
        display_name = package_name.replace("_", "-")
        
        if check_package(package_name):
            print(f"✅ {display_name:30s} - Installed")
            installed.append(package)
        else:
            print(f"❌ {display_name:30s} - Missing")
            missing.append(package)
    
    print(f"\n{'='*70}")
    print(f"  Summary: {len(installed)} installed, {len(missing)} missing")
    print(f"{'='*70}\n")
    
    if missing:
        print("Missing packages detected!")
        response = input("Would you like to install missing packages? (y/n): ").strip().lower()
        
        if response == 'y':
            print("\nInstalling missing packages...\n")
            for package in missing:
                print(f"Installing {package}...")
                if install_package(package):
                    print(f"✅ {package} installed successfully")
                else:
                    print(f"❌ Failed to install {package}")
            print("\n✅ Installation complete!")
        else:
            print("\n⚠️  Some packages are missing. The system may not work correctly.")
            print("   You can install them later with: pip install -r requirements.txt")
    else:
        print("✅ All dependencies are installed!")
    
    print("\n" + "="*70)
    print("  Dependency Check Complete")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()

