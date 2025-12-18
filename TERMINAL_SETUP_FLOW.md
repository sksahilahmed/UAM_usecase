# Terminal Setup Flow - Complete Guide

## Overview

The system now has **automatic terminal-based setup** that runs when you execute `main.py`. The setup is intelligent - it only asks questions if training history is missing.

## Complete Flow

### First Time Setup (Training History Missing)

```
1. User runs: python main.py
   ↓
2. System checks prerequisites:
   - ✅ .env file exists with OPENAI_API_KEY
   - ✅ master_tracker.xlsx exists in data/ folder
   ↓
3. System checks training history:
   - ❌ training_config.json NOT found
   ↓
4. System loads master tracker:
   - Reads master_tracker.xlsx
   - Analyzes all rules, prerequisites, permissions
   - Shows summary to user
   ↓
5. AI reads context:
   - Understands permission types
   - Understands prerequisites
   - Understands validation rules structure
   ↓
6. System asks questions in TERMINAL:
   - Question 1: Forms required for requests
   - Question 2: Validation rules
   - Question 3: Auto-approval criteria
   - Question 4: Rejection criteria
   - Question 5: Special cases
   ↓
7. User answers all questions
   ↓
8. System trains:
   - Saves responses to data/training_config.json
   - Syncs master tracker to database
   - Creates training configuration
   ↓
9. Setup complete!
   - System is ready to use
   - Training history saved
```

### Subsequent Runs (Training History Exists)

```
1. User runs: python main.py
   ↓
2. System checks prerequisites:
   - ✅ .env file exists
   - ✅ master_tracker.xlsx exists
   ↓
3. System checks training history:
   - ✅ training_config.json FOUND
   ↓
4. System loads training:
   - Loads training_config.json
   - Loads master tracker rules
   - System ready immediately
   ↓
5. NO QUESTIONS ASKED!
   - Skips setup
   - Goes directly to main functionality
```

## Key Features

### ✅ Automatic Detection
- Automatically detects if setup is needed
- Only asks questions if training history is missing

### ✅ Smart Caching
- Training history saved in `data/training_config.json`
- Never asks questions twice
- Only re-asks if history is deleted

### ✅ Complete Context
- AI reads entire master tracker
- Understands all rules and prerequisites
- Questions are context-aware

### ✅ Terminal-Based
- All setup happens in terminal
- No UI required for setup
- Simple Q&A format

## File Structure

```
project/
├── .env                          # Your API keys (create this)
├── data/
│   ├── master_tracker.xlsx      # Your Excel file (place here)
│   └── training_config.json    # Auto-generated (training history)
├── main.py                       # Run this - setup happens automatically
├── setup_terminal.py            # Terminal setup functions
└── ...
```

## What You Need to Do

1. **Create `.env` file** with your OpenAI API key
2. **Place `master_tracker.xlsx`** in `data/` folder
3. **Run `python main.py`**
4. **Answer questions** (first time only)
5. **Done!** System is ready

## Training History

The training history is saved in `data/training_config.json` and contains:
- Forms required
- Validation rules
- Auto-approval criteria
- Rejection criteria
- Special cases
- Master tracker analysis

### To Re-train:
Simply delete `data/training_config.json` and run `python main.py` again.

## Example Terminal Output

### First Run:
```
======================================================================
  UAM Agentic AI System - Initial Setup Required
======================================================================

✅ Prerequisites check passed
   - .env file found with API key
   - Master tracker found: data/master_tracker.xlsx

──────────────────────────────────────────────────────────────────────
  Step 1: Loading Master Tracker
──────────────────────────────────────────────────────────────────────

📁 Loading master tracker from: data/master_tracker.xlsx
✅ Master tracker loaded successfully!
   - Total rules found: 15

📊 Analysis Summary:
   - Permission types: 3
   - Auto-grant enabled: 8
   - Common prerequisites: 12

──────────────────────────────────────────────────────────────────────
  Step 2: Training Configuration
──────────────────────────────────────────────────────────────────────

Question 1/5
======================================================================
Based on the master tracker, I've identified several permission types...
Your answer (Required): Access Request Form, Manager Approval Form

✅ Answer saved.

[... more questions ...]

──────────────────────────────────────────────────────────────────────
  Step 3: Training AI System
──────────────────────────────────────────────────────────────────────

🤖 Training AI system with your responses...
✅ Training completed successfully!

======================================================================
  ✅ Setup Complete! System is now ready.
======================================================================
```

### Subsequent Runs:
```
✅ System already trained. Loading configuration...

UAM Agentic AI System - Test Interface
============================================================
[... main functionality ...]
```

## Troubleshooting

### Questions asked every time?
- Check if `data/training_config.json` exists
- If missing, training wasn't completed
- Delete it and run again to re-train

### Setup fails?
- Check `.env` file has valid API key
- Check `master_tracker.xlsx` is in `data/` folder
- Check file permissions

### Want to change training?
- Delete `data/training_config.json`
- Run `python main.py` again
- Answer questions with new responses

