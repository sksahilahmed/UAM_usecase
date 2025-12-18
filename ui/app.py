"""Streamlit UI for UAM Agentic AI System"""
import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path
import shutil

# Add parent directory to path (project root)
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.uam_agent import UAMAgent
from database.models import init_database
from excel_parser.master_tracker import MasterTrackerParser
from database.user_context import UserContextManager
from database.models import get_db_session, Request, User
from setup.trainer import SetupTrainer
from database.audit_log import AuditLogger
from utils.logger import logger
import plotly.express as px
from config import MASTER_TRACKER_PATH, DATA_DIR

# Page configuration
st.set_page_config(
    page_title="UAM Agentic AI System",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .decision-badge {
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-weight: bold;
        display: inline-block;
        margin: 0.5rem 0;
    }
    .granted {
        background-color: #28a745;
        color: white;
    }
    .ticket {
        background-color: #ffc107;
        color: black;
    }
    .pending {
        background-color: #6c757d;
        color: white;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.agent = None
    st.session_state.trainer = None
    st.session_state.setup_complete = False
    st.session_state.setup_step = 1
    st.session_state.master_tracker_loaded = False
    st.session_state.questions_answered = False
    st.session_state.training_responses = {}

# Initialize database and trainer
init_database()
if st.session_state.trainer is None:
    st.session_state.trainer = SetupTrainer()

# Check if system is trained
if st.session_state.trainer.is_trained():
    st.session_state.setup_complete = True

def initialize_system():
    """Initialize the UAM system"""
    try:
        if not st.session_state.initialized:
            with st.spinner("Initializing UAM system..."):
                parser = MasterTrackerParser()
                parser.sync_to_database()
                st.session_state.agent = UAMAgent()
                st.session_state.initialized = True
            st.success("System initialized successfully!")
    except Exception as e:
        st.error(f"Error initializing system: {e}")
        logger.error(f"Initialization error: {e}")

def get_decision_badge_class(decision):
    """Get CSS class for decision badge"""
    if decision == "grant" or decision == "granted":
        return "granted"
    elif "ticket" in decision.lower():
        return "ticket"
    else:
        return "pending"

# Main content - Setup flow or main UI
if not st.session_state.setup_complete:
    # SETUP FLOW
    st.markdown('<h1 class="main-header">🚀 UAM System Setup</h1>', unsafe_allow_html=True)
    st.info("Welcome! Let's set up your UAM Agentic AI system. This will only take a few minutes.")
    
    # Step 1: Upload Master Tracker
    if st.session_state.setup_step == 1:
        st.markdown("### Step 1: Upload Master Tracker Excel File")
        st.markdown("""
        Please upload your master tracker Excel file. The AI will analyze it to understand:
        - Permission types and rules
        - Pre-requisites
        - Validation criteria
        """)
        
        uploaded_file = st.file_uploader(
            "Choose Excel file (master_tracker.xlsx)",
            type=['xlsx', 'xls'],
            help="Upload your master tracker Excel file"
        )
        
        if uploaded_file is not None:
            # Save uploaded file
            DATA_DIR.mkdir(exist_ok=True)
            file_path = DATA_DIR / "master_tracker.xlsx"
            
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"✅ File uploaded: {uploaded_file.name}")
            
            # Load and analyze
            with st.spinner("Analyzing master tracker..."):
                result = st.session_state.trainer.load_master_tracker(file_path)
                
                if result["success"]:
                    st.session_state.master_tracker_loaded = True
                    st.session_state.setup_step = 2
                    
                    st.success(f"✅ Master tracker loaded successfully!")
                    st.markdown("#### Analysis Summary:")
                    analysis = result["analysis"]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Rules", result["rules_count"])
                    with col2:
                        st.metric("Permission Types", len(analysis.get("permission_types", {})))
                    with col3:
                        st.metric("Auto-Grant Enabled", analysis.get("auto_grant_enabled_count", 0))
                    
                    # Show sample rules
                    if result.get("rules"):
                        with st.expander("📋 Preview Rules (First 5)"):
                            st.json(result["rules"][:5])
                    
                    st.rerun()
                else:
                    st.error(f"❌ Error loading master tracker: {result.get('error')}")
        
        # Alternative: Use existing file
        if MASTER_TRACKER_PATH.exists():
            st.markdown("---")
            st.info(f"📁 Found existing master tracker at: `{MASTER_TRACKER_PATH}`")
            if st.button("Use Existing File", use_container_width=True):
                with st.spinner("Loading existing master tracker..."):
                    result = st.session_state.trainer.load_master_tracker()
                    if result["success"]:
                        st.session_state.master_tracker_loaded = True
                        st.session_state.setup_step = 2
                        st.rerun()
    
    # Step 2: Answer Questions
    elif st.session_state.setup_step == 2:
        st.markdown("### Step 2: Configure Validation Rules")
        st.markdown("""
        The AI needs to understand your validation rules. Please answer these questions to help it learn:
        """)
        
        # Get questions
        analysis = st.session_state.trainer._analyze_master_tracker(
            st.session_state.trainer.master_tracker_data,
            st.session_state.trainer.parser.parse_permission_rules()
        )
        questions = st.session_state.trainer.generate_questions(analysis)
        
        with st.form("training_questions_form"):
            responses = {}
            
            for q in questions:
                if q["type"] == "text":
                    responses[q["id"]] = st.text_input(
                        q["question"],
                        help=q.get("help_text", ""),
                        key=q["id"]
                    )
                elif q["type"] == "textarea":
                    responses[q["id"]] = st.text_area(
                        q["question"],
                        help=q.get("help_text", ""),
                        height=100,
                        key=q["id"]
                    )
            
            submitted = st.form_submit_button("✅ Complete Training", use_container_width=True)
            
            if submitted:
                # Validate required fields
                required_questions = [q for q in questions if q.get("required", False)]
                missing = [q["id"] for q in required_questions if not responses.get(q["id"])]
                
                if missing:
                    st.error(f"Please answer all required questions. Missing: {', '.join(missing)}")
                else:
                    # Train system
                    with st.spinner("Training AI system..."):
                        result = st.session_state.trainer.train_with_user_responses(questions, responses)
                        
                        if result["success"]:
                            st.session_state.setup_complete = True
                            st.session_state.questions_answered = True
                            st.session_state.training_responses = responses
                            
                            st.success("🎉 Training completed successfully!")
                            st.balloons()
                            
                            st.info("The system is now ready. You can start using it!")
                            if st.button("🚀 Go to Main Interface", use_container_width=True):
                                st.session_state.setup_step = 3
                                initialize_system()
                                st.rerun()
                        else:
                            st.error(f"Error during training: {result.get('error')}")

# Main UI (after setup)
else:
    # Sidebar
    with st.sidebar:
        st.header("🔐 UAM System")
        st.markdown("---")
        
        # Show training status
        summary = st.session_state.trainer.get_training_summary()
        if summary["trained"]:
            st.success("✅ System Trained")
            st.caption(f"Rules: {summary['rules_loaded']}")
        
        if st.button("🔄 Re-initialize System", use_container_width=True):
            st.session_state.initialized = False
            initialize_system()
            st.rerun()
        
        if st.button("⚙️ Re-run Setup", use_container_width=True):
            st.session_state.setup_complete = False
            st.session_state.setup_step = 1
            st.rerun()
        
        st.markdown("---")
        st.markdown("### Navigation")
        page = st.radio(
            "Select Page",
            ["📝 New Request", "📊 Dashboard", "👤 User Lookup", "📋 Audit Logs", "⚙️ Configuration"],
            label_visibility="collapsed"
        )
    
    # Initialize agent if needed
    if not st.session_state.initialized:
        initialize_system()
    
    if not st.session_state.initialized:
        st.warning("Please initialize the system from the sidebar.")
    else:
        if page == "📝 New Request":
        st.markdown('<h1 class="main-header">🔐 User Access Request</h1>', unsafe_allow_html=True)
        
        with st.form("access_request_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("User Information")
                user_id = st.text_input("User ID *", placeholder="EMP001")
                username = st.text_input("Username", placeholder="john.doe")
                email = st.text_input("Email", placeholder="john.doe@company.com")
                department = st.selectbox("Department", 
                    ["Sales", "IT", "HR", "Finance", "Support", "Operations", "Other"])
                role = st.text_input("Role", placeholder="Sales Representative")
            
            with col2:
                st.subheader("Request Details")
                request_type = st.selectbox("Request Type *",
                    ["application_access", "system_access", "database_access", "other"])
                requested_permission = st.text_input("Requested Permission *", 
                    placeholder="Salesforce Access")
                description = st.text_area("Description *", 
                    placeholder="Need access for managing customer accounts", height=100)
                
                st.subheader("Additional Context")
                security_clearance = st.slider("Security Clearance Level", 0, 5, 1)
                trainings_completed = st.multiselect("Completed Trainings",
                    ["Security Training", "Salesforce Basics", "Database Training", 
                     "ServiceNow Training", "Linux Basics"])
            
            submitted = st.form_submit_button("🚀 Submit Request", use_container_width=True)
            
            if submitted:
                if not user_id or not requested_permission or not description:
                    st.error("Please fill in all required fields (marked with *)")
                else:
                    with st.spinner("Processing request..."):
                        try:
                            user_info = {
                                "username": username if username else None,
                                "email": email if email else None,
                                "department": department,
                                "role": role if role else None,
                                "context_data": {
                                    "security_clearance_level": security_clearance,
                                    "completed_trainings": trainings_completed
                                }
                            }
                            
                            result = st.session_state.agent.process_request(
                                user_id=user_id,
                                request_type=request_type,
                                requested_permission=requested_permission,
                                description=description,
                                user_info=user_info
                            )
                            
                            st.success("Request processed successfully!")
                            
                            # Display results
                            st.markdown("---")
                            st.markdown("## 📋 Request Result")
                            
                            col1, col2, col3 = st.columns(3)
                            
                            decision_class = get_decision_badge_class(result['decision'])
                            with col1:
                                st.metric("Decision", result['decision'].upper())
                                st.markdown(f'<div class="decision-badge {decision_class}">{result["status"].upper()}</div>', 
                                          unsafe_allow_html=True)
                            
                            with col2:
                                st.metric("Priority Score", f"{result['priority_score']}/100")
                                st.metric("Confidence", f"{result['confidence']:.1%}")
                            
                            with col3:
                                if result.get('ticket_id'):
                                    st.metric("Ticket ID", result['ticket_id'])
                                else:
                                    st.metric("Request ID", result['request_id'])
                            
                            # Reasoning
                            st.markdown("### 💭 Decision Reasoning")
                            st.info(result['reasoning'])
                            
                            # Pre-requisites status
                            if result.get('pre_requisites_status'):
                                st.markdown("### ✅ Pre-requisites Status")
                                prereqs_df = pd.DataFrame([
                                    {
                                        "Pre-requisite": prereq,
                                        "Status": "✓ Met" if status['met'] else "✗ Not Met",
                                        "Details": status.get('details', '')
                                    }
                                    for prereq, status in result['pre_requisites_status'].items()
                                ])
                                st.dataframe(prereqs_df, use_container_width=True, hide_index=True)
                            
                        except Exception as e:
                            st.error(f"Error processing request: {e}")
                            logger.error(f"Request processing error: {e}")
    
    elif page == "📊 Dashboard":
        st.markdown('<h1 class="main-header">📊 Dashboard</h1>', unsafe_allow_html=True)
        
        db = get_db_session()
        try:
            # Get statistics
            total_requests = db.query(Request).count()
            granted_requests = db.query(Request).filter(Request.status == "granted").count()
            ticket_requests = db.query(Request).filter(Request.status == "ticket_created").count()
            total_users = db.query(User).count()
            
            # Metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Requests", total_requests)
            with col2:
                st.metric("Auto-Granted", granted_requests, 
                         delta=f"{(granted_requests/total_requests*100) if total_requests > 0 else 0:.1f}%")
            with col3:
                st.metric("Tickets Created", ticket_requests)
            with col4:
                st.metric("Total Users", total_users)
            
            st.markdown("---")
            
            # Recent requests table
            st.subheader("📋 Recent Requests")
            recent_requests = db.query(Request).order_by(Request.created_at.desc()).limit(20).all()
            
            if recent_requests:
                requests_data = []
                for req in recent_requests:
                    requests_data.append({
                        "Request ID": req.id,
                        "User ID": req.user_id,
                        "Permission": req.requested_permission,
                        "Priority Score": req.priority_score,
                        "Status": req.status,
                        "Auto-Granted": "Yes" if req.auto_granted else "No",
                        "Created At": req.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                df = pd.DataFrame(requests_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Charts
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Requests by Status")
                    status_counts = df['Status'].value_counts()
                    fig_status = px.pie(
                        values=status_counts.values,
                        names=status_counts.index,
                        title="Request Status Distribution"
                    )
                    st.plotly_chart(fig_status, use_container_width=True)
                
                with col2:
                    st.subheader("Priority Score Distribution")
                    fig_priority = px.histogram(
                        df, x="Priority Score",
                        nbins=20,
                        title="Priority Score Distribution"
                    )
                    st.plotly_chart(fig_priority, use_container_width=True)
            else:
                st.info("No requests found. Submit a request to see data here.")
            
        except Exception as e:
            st.error(f"Error loading dashboard data: {e}")
            logger.error(f"Dashboard error: {e}")
        finally:
            db.close()
    
    elif page == "👤 User Lookup":
        st.markdown('<h1 class="main-header">👤 User Access Summary</h1>', unsafe_allow_html=True)
        
        user_id_search = st.text_input("Enter User ID", placeholder="EMP001")
        
        if st.button("🔍 Search", use_container_width=True):
            if user_id_search:
                try:
                    summary = st.session_state.agent.get_user_access_summary(user_id_search)
                    
                    if "error" in summary:
                        st.error("User not found")
                    else:
                        # User information
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("### User Information")
                            st.write(f"**User ID:** {summary['user_id']}")
                            st.write(f"**Username:** {summary.get('username', 'N/A')}")
                            st.write(f"**Department:** {summary.get('department', 'N/A')}")
                            st.write(f"**Role:** {summary.get('role', 'N/A')}")
                        
                        with col2:
                            st.markdown("### Access Summary")
                            st.metric("Total Permissions", summary.get('total_permissions', 0))
                            st.metric("Total Requests", summary.get('total_requests', 0))
                        
                        # Current permissions
                        if summary.get('current_permissions'):
                            st.markdown("### 🔑 Current Permissions")
                            perms_df = pd.DataFrame([
                                {
                                    "Permission": perm,
                                    "Granted At": details.get('granted_at', 'N/A'),
                                    "Status": details.get('status', 'N/A')
                                }
                                for perm, details in summary['current_permissions'].items()
                            ])
                            st.dataframe(perms_df, use_container_width=True, hide_index=True)
                        
                        # Recent requests
                        if summary.get('recent_requests'):
                            st.markdown("### 📋 Recent Requests")
                            requests_df = pd.DataFrame(summary['recent_requests'])
                            st.dataframe(requests_df, use_container_width=True, hide_index=True)
                        
                except Exception as e:
                    st.error(f"Error retrieving user summary: {e}")
                    logger.error(f"User lookup error: {e}")
            else:
                st.warning("Please enter a User ID")
    
    elif page == "📋 Audit Logs":
        st.markdown('<h1 class="main-header">📋 Audit Logs</h1>', unsafe_allow_html=True)
        
        audit_logger = AuditLogger()
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            entity_type_filter = st.selectbox(
                "Filter by Entity Type",
                ["All", "request", "system", "config", "user"],
                index=0
            )
        with col2:
            limit = st.slider("Number of records", 10, 500, 100)
        
        # Get audit logs
        entity_type = None if entity_type_filter == "All" else entity_type_filter
        logs = audit_logger.get_audit_history(entity_type=entity_type, limit=limit)
        
        if logs:
            st.metric("Total Audit Records", len(logs))
            
            # Convert to DataFrame
            logs_df = pd.DataFrame(logs)
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
            logs_df = logs_df.sort_values('timestamp', ascending=False)
            
            # Display table
            st.subheader("Audit History")
            display_df = logs_df[['timestamp', 'action_type', 'entity_type', 'entity_id', 
                                 'user_id', 'decision', 'reasoning']].copy()
            display_df.columns = ['Timestamp', 'Action', 'Entity Type', 'Entity ID', 
                                 'User ID', 'Decision', 'Reasoning']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # Show details in expander
            if st.checkbox("Show Full Details"):
                selected_idx = st.selectbox("Select record", range(len(logs)))
                if selected_idx is not None:
                    log = logs[selected_idx]
                    st.json(log)
        else:
            st.info("No audit logs found.")
        
        audit_logger.close()
    
    elif page == "⚙️ Configuration":
        st.markdown('<h1 class="main-header">⚙️ Configuration</h1>', unsafe_allow_html=True)
        
        st.subheader("📁 Master Tracker")
        st.info("The master tracker Excel file is located at: `data/master_tracker.xlsx`")
        
        if st.button("🔄 Sync Master Tracker", use_container_width=True):
            with st.spinner("Syncing master tracker..."):
                try:
                    parser = MasterTrackerParser()
                    parser.sync_to_database()
                    st.success("Master tracker synced successfully!")
                except Exception as e:
                    st.error(f"Error syncing master tracker: {e}")
        
        st.markdown("---")
        st.subheader("📊 System Information")
        
        from config import (
            AUTO_GRANT_THRESHOLD, REQUIRE_APPROVAL_THRESHOLD,
            USE_AI_REASONING, MODEL_NAME, TEMPERATURE
        )
        
        config_data = {
            "Setting": [
                "Auto-Grant Threshold",
                "Require Approval Threshold",
                "AI Reasoning Enabled",
                "Model Name",
                "Temperature"
            ],
            "Value": [
                AUTO_GRANT_THRESHOLD,
                REQUIRE_APPROVAL_THRESHOLD,
                "Yes" if USE_AI_REASONING else "No",
                MODEL_NAME,
                TEMPERATURE
            ]
        }
        
        config_df = pd.DataFrame(config_data)
        st.dataframe(config_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("📝 About")
        st.markdown("""
        **UAM Agentic AI System**
        
        This system automates user access management by:
        - Analyzing user requests against pre-requisites
        - Calculating priority scores
        - Making intelligent decisions (auto-grant or create ticket)
        - Using AI for enhanced reasoning
        
        **Configuration:** Edit `.env` file to configure API keys and thresholds.
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6c757d;'>
    UAM Agentic AI System | Built with Streamlit
</div>
""", unsafe_allow_html=True)

