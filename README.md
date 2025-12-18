# UAM Agentic AI System

## Overview
User Access Management (UAM) Agentic AI system that processes user access requests by:
1. Analyzing user request context
2. Checking historical data and permissions
3. Evaluating against pre-requisites and rules
4. Automatically granting access or creating tickets based on priority

## Architecture

```
┌─────────────────┐
│  User Request   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Request Handler │
└────────┬────────┘
         │
         ├──────────┐
         │          │
         ▼          ▼
┌──────────────┐  ┌──────────────────┐
│   Database   │  │  Excel Master    │
│ (User Context│  │    Tracker       │
│   & History) │  │ (Pre-requisites) │
└──────┬───────┘  └─────────┬────────┘
       │                    │
       │                    │
       └──────────┬─────────┘
                  │
                  ▼
         ┌─────────────────┐
         │   AI Agent      │
         │ Decision Engine │
         └────────┬────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
  ┌──────────┐      ┌──────────┐
  │   Grant  │      │  Create  │
  │  Access  │      │  Ticket  │
  └──────────┘      └──────────┘
```

## Components

### 1. Excel Master Tracker Parser
- Reads master Excel sheet with:
  - Permission types and their pre-requisites
  - Rules/criteria for granting permissions
  - Priority levels

### 2. Database Module
- Stores user request history
- Tracks user permissions and context
- Provides historical data for AI decision making

### 3. AI Agent Core
- Processes requests using LLM/AI
- Makes decisions based on:
  - User history and context
  - Pre-requisites from master tracker
  - Priority levels
  - Risk assessment

### 4. Decision Engine
- Evaluates if access can be auto-granted
- Determines when to create a ticket
- Applies business rules and policies

### 5. Request Handler
- Receives and validates user requests
- Orchestrates the workflow
- Returns responses/actions

## Setup

### Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Add your OpenAI API key: `OPENAI_API_KEY=sk-your-key-here`
   - Get your key from: https://platform.openai.com/api-keys

3. **Run the UI:**
```bash
python run_ui.py
# Or: streamlit run ui/app.py
```

4. **Access the UI:**
   - Open browser to: http://localhost:8501
   - Initialize system from sidebar
   - Start submitting requests!

### Alternative: Command Line
```bash
python main.py  # Run with example scenarios
```

See `SETUP.md` for detailed setup instructions.

## Features

### ✅ Implemented
- ✅ Excel Master Tracker integration
- ✅ User context and history tracking
- ✅ Priority-based decision engine
- ✅ Pre-requisite validation
- ✅ AI-powered reasoning (OpenAI)
- ✅ Streamlit web UI
- ✅ Dashboard and analytics
- ✅ User lookup and access summary

### 🚀 Future Enhancements
- ServiceNow API integration for ticket creation
- CrewAI multi-agent orchestration
- Enhanced AI capabilities with RAG
- Audit logging
- REST API endpoints
- Email notifications

