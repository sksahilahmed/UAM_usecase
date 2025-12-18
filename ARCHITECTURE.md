# UAM Agentic AI - Architecture & Approach

## System Overview

The UAM (User Access Management) Agentic AI system automates the process of evaluating and granting user access requests by leveraging:
1. **Historical context** - User's previous requests and permissions
2. **Master rules** - Pre-requisites and criteria from Excel master tracker
3. **AI decision making** - Intelligent evaluation based on multiple factors
4. **Automated actions** - Auto-grant or ticket creation based on priority

## Key Components

### 1. Excel Master Tracker Parser (`excel_parser/master_tracker.py`)
- **Purpose**: Reads and parses the Excel master tracker file
- **Input**: Excel file with columns:
  - Permission_Type
  - Permission_Name
  - Pre_Requisites (comma-separated or JSON)
  - Criteria
  - Priority_Level
  - Auto_Grant (yes/no)
- **Output**: Structured permission rules synced to database
- **Features**:
  - Flexible column name matching
  - Handles JSON or comma-separated lists
  - Creates sample structure if file doesn't exist

### 2. Database Layer (`database/`)
- **Models** (`models.py`):
  - `User`: Stores user information and current permissions
  - `Request`: Tracks all access requests with decisions
  - `PermissionRule`: Stores rules from master tracker
- **User Context Manager** (`user_context.py`):
  - Manages user data and history
  - Tracks permissions
  - Provides context for AI decisions

### 3. Decision Engine (`agents/decision_engine.py`)
- **Pre-requisite Checking**:
  - Validates user credentials
  - Checks department, role, training
  - Verifies security clearance
  - Validates manager approvals (placeholder)
- **Priority Scoring** (0-100):
  - Base score: 50
  - Pre-requisites met: +0-30
  - Priority level: +0-20
  - User history: +10
  - Auto-grant enabled: +10
- **Decision Logic**:
  - **Grant**: Score ≥ 80 AND auto-grant enabled AND 80%+ pre-requisites met
  - **Create Ticket**: Score ≥ 50 OR missing critical pre-requisites
  - **Reject/Pending**: Low score or critical failures

### 4. UAM Agent (`agents/uam_agent.py`)
- **Main orchestrator**:
  - Receives user requests
  - Coordinates evaluation
  - Executes decisions
  - Updates records
- **Ticket Creation**:
  - Currently simulated
  - Ready for ServiceNow API integration

## Workflow

```
1. User Request → Request Handler
2. Load User Context from Database
3. Load Permission Rules from Database (synced from Excel)
4. Check Pre-requisites
5. Calculate Priority Score
6. Make Decision (Grant/Ticket/Reject)
7. Execute Action:
   - Grant: Update user permissions
   - Ticket: Create ServiceNow ticket (future)
8. Log Result
9. Return Response
```

## Data Flow

### Master Tracker Sync
```
Excel File → Parser → Database (PermissionRule table)
```

### Request Processing
```
User Request → UAM Agent → Decision Engine → Database → Action → Response
                ↓              ↓
        User Context    Permission Rules
```

## Priority & Decision Matrix

| Priority Score | Pre-requisites Met | Auto-Grant Enabled | Decision |
|---------------|-------------------|-------------------|----------|
| ≥ 80 | ≥ 80% | Yes | **Grant** |
| ≥ 80 | < 80% | Yes | **Create Ticket** |
| ≥ 80 | Any | No | **Create Ticket** |
| 50-79 | Any | Any | **Create Ticket** |
| < 50 | Any | Any | **Create Ticket** |

## Pre-requisite Types

The system recognizes common pre-requisite patterns:
- **Valid Employee ID**: Checks for user_id
- **Department**: Validates department assignment
- **Manager Approval**: Flagged (requires external system)
- **Security Clearance**: Checks clearance level (≥2 for sensitive access)
- **Training**: Validates completed trainings
- **Role**: Checks user role

## Future Enhancements

### Phase 1: ServiceNow Integration
```python
# agents/servicenow_client.py
class ServiceNowClient:
    def create_incident(self, request_data):
        # Create ticket via ServiceNow REST API
        pass
    
    def get_ticket_status(self, ticket_id):
        # Check ticket status
        pass
```

### Phase 2: Enhanced AI
- **LLM Integration**: Use GPT-4 for better context understanding
- **RAG (Retrieval Augmented Generation)**: Use historical data for better decisions
- **Natural Language Processing**: Parse unstructured request descriptions

### Phase 3: Advanced Features
- **Risk Assessment**: ML-based risk scoring
- **Approval Workflows**: Multi-level approvals
- **Audit Logging**: Comprehensive audit trail
- **Dashboard**: Real-time monitoring and analytics
- **Notifications**: Email/Slack notifications

## Integration Points

### Current
- ✅ Excel file (master tracker)
- ✅ SQLite database
- ⏳ ServiceNow API (planned)

### API Endpoints (Future REST API)
```
POST /api/v1/requests
  - Create access request
  
GET /api/v1/users/{user_id}/summary
  - Get user access summary
  
GET /api/v1/requests/{request_id}
  - Get request status
  
POST /api/v1/sync/master-tracker
  - Sync Excel to database
```

## Configuration

Key configuration in `config.py`:
- `AUTO_GRANT_THRESHOLD`: 80 (minimum score for auto-grant)
- `REQUIRE_APPROVAL_THRESHOLD`: 50 (minimum score to create ticket)
- Database path
- Excel file path
- API keys (when adding LLM)

## Testing Approach

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test full workflow
3. **Test Data**: Use sample Excel and test users
4. **Mock ServiceNow**: Simulate ticket creation

## Deployment Considerations

1. **Database**: Upgrade from SQLite to PostgreSQL for production
2. **Scalability**: Add caching (Redis) for frequently accessed data
3. **Security**: Encrypt sensitive data, add authentication
4. **Monitoring**: Add logging, metrics, alerts
5. **Backup**: Regular database backups

