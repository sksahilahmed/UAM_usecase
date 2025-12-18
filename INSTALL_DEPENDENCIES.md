# Install Dependencies

## Quick Install

If you're getting "no module named loguru" or other import errors, install all dependencies:

```bash
pip install -r requirements.txt
```

## Manual Install (if pip install fails)

Install each package individually:

```bash
pip install openpyxl>=3.1.2
pip install pandas>=2.1.0
pip install python-dotenv>=1.0.0
pip install sqlalchemy>=2.0.0
pip install pydantic>=2.5.0
pip install openai>=1.3.0
pip install langchain>=0.1.0
pip install langchain-openai>=0.0.2
pip install loguru>=0.7.2
pip install crewai>=0.1.0
pip install streamlit>=1.28.0
pip install plotly>=5.17.0
```

## Fallback Logger

The system now has a fallback logger. If `loguru` is not installed, it will use Python's standard `logging` module instead. You'll see a warning message but the system will still work.

However, it's recommended to install all dependencies for full functionality.

## Verify Installation

After installing, verify by running:

```bash
python -c "import loguru; print('loguru installed successfully')"
```

Or test the main file:

```bash
python main.py
```

If you see "⚠️ Warning: loguru not installed", the fallback logger is working, but you should still install loguru for better logging features.

