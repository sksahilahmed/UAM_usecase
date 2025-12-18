# Quick Setup Guide

## What You Need to Do

### 1. Create `.env` File
Create a `.env` file in the project root with:
```env
OPENAI_API_KEY=your-actual-api-key-here
CREWAI_OPENAI_API_KEY=your-actual-api-key-here
MODEL_NAME=gpt-4
TEMPERATURE=0.3
AUTO_GRANT_THRESHOLD=80
REQUIRE_APPROVAL_THRESHOLD=50
USE_AI_REASONING=true
```

### 2. Place Master Tracker Excel File
Place your `master_tracker.xlsx` file in the `data/` folder:
```
data/master_tracker.xlsx
```

### 3. Run Main File
Simply run:
```bash
python main.py
```

## What Happens Automatically

### First Run (Setup Required)
1. ✅ System checks for `.env` file and API key
2. ✅ System checks for `master_tracker.xlsx` file
3. ✅ System loads and analyzes the master tracker
4. ✅ AI reads all the context from master tracker
5. ✅ System asks you questions in terminal:
   - Forms required for requests
   - Validation rules
   - Auto-approval criteria
   - Rejection criteria
   - Special cases
6. ✅ You answer the questions
7. ✅ System trains itself with your responses
8. ✅ Training history is saved
9. ✅ System is ready!

### Subsequent Runs (Already Trained)
1. ✅ System checks if training history exists
2. ✅ If exists, skips questions and loads training
3. ✅ System is ready immediately!

## That's It!

You only need to:
- ✅ Create `.env` file
- ✅ Place `master_tracker.xlsx` in `data/` folder
- ✅ Run `python main.py`

Everything else is automatic!

## Notes

- **Training history is saved** in `data/training_config.json`
- **Questions are only asked once** (first time)
- **If training history is missing**, questions will be asked again
- **You can re-run setup** by deleting `data/training_config.json`

## Troubleshooting

### "OPENAI_API_KEY not found"
- Make sure `.env` file exists in project root
- Check that `OPENAI_API_KEY=your-key` is in the file

### "Master tracker not found"
- Place `master_tracker.xlsx` in `data/` folder
- Make sure the file name is exactly `master_tracker.xlsx`

### "Questions asked every time"
- Check if `data/training_config.json` exists
- If it doesn't exist, training wasn't completed successfully
- Delete it and run again to re-train

