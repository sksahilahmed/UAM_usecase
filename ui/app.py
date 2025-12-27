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
    st.session_state.chat_messages = []
    st.session_state.chat_client = None

# Initialize database (minimal - just ensure it exists)
init_database()

def initialize_system():
    """Initialize the UAM system - assumes setup is already done via main.py"""
    try:
        if not st.session_state.initialized:
            with st.spinner("Initializing UAM system..."):
                # Just create the agent - no setup/validation here
                st.session_state.agent = UAMAgent()
                st.session_state.initialized = True
            st.success("System ready!")
    except Exception as e:
        st.error(f"Error initializing system: {e}")
        logger.error(f"Initialization error: {e}")

def initialize_chat_client():
    """Initialize OpenAI client for chat functionality"""
    if st.session_state.chat_client is None:
        try:
            from utils.openai_client import get_openai_client, OPENAI_AVAILABLE
            from config import USE_AZURE_OPENAI, OPENAI_API_KEY, AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
            
            if not OPENAI_AVAILABLE:
                return None
            
            api_key = AZURE_OPENAI_API_KEY if USE_AZURE_OPENAI else OPENAI_API_KEY
            api_key = api_key or OPENAI_API_KEY  # Fallback
            
            if not api_key or api_key.strip() == "":
                return None
            
            st.session_state.chat_client = get_openai_client(
                api_key=api_key,
                azure_endpoint=AZURE_OPENAI_ENDPOINT if USE_AZURE_OPENAI else None,
                api_version=AZURE_OPENAI_API_VERSION if USE_AZURE_OPENAI else None,
                deployment_name=AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else None,
                use_azure=USE_AZURE_OPENAI
            )
        except Exception as e:
            logger.error(f"Error initializing chat client: {e}")
            return None
    return st.session_state.chat_client

def get_chat_system_prompt():
    """Get system prompt for UAM AI assistant"""
    return """You are an AI assistant for the User Access Management (UAM) system. 
Your role is to help users understand:
- Access request processes and requirements
- Permission rules and prerequisites
- Training requirements for different roles
- How the UAM system works
- General questions about access management policies

Be helpful, professional, and provide clear, concise answers. If you don't know something specific about the system configuration, say so honestly."""

def get_decision_badge_class(decision):
    """Get CSS class for decision badge"""
    if decision == "grant" or decision == "granted":
        return "granted"
    elif decision == "ask_for_more_info":
        return "pending"
    elif "ticket" in decision.lower():
        return "ticket"
    else:
        return "pending"

# Main UI - Only for submitting requests and viewing decisions
# Setup/validation should be done via main.py
# Sidebar
with st.sidebar:
    st.header("🔐 UAM System")
    st.markdown("---")
    st.info("💡 Run `python main.py` for setup/validation")
    st.markdown("---")
    
    if st.button("🔄 Re-initialize System", use_container_width=True):
        st.session_state.initialized = False
        initialize_system()
        st.rerun()
    
    st.markdown("---")
    st.markdown("### Navigation")
    page = st.radio(
        "Select Page",
        ["📝 New Request", "💬 AI Assistant", "📊 Dashboard", "👤 User Lookup", "📋 Audit Logs"],
        label_visibility="collapsed"
    )

# Initialize agent if needed
if not st.session_state.initialized:
    initialize_system()

if not st.session_state.initialized:
    st.error("❌ System not initialized. Please run `python main.py` first to complete setup.")
else:
    if page == "📝 New Request":
        st.markdown('<h1 class="main-header">🔐 User Access Request</h1>', unsafe_allow_html=True)
            
        # Load master tracker form fields, roles, and trainings
        try:
            from utils.master_tracker_fields import get_master_tracker_form_fields, get_trainings_from_master_tracker, get_roles_from_master_tracker
            master_tracker_fields = get_master_tracker_form_fields()
            available_trainings = get_trainings_from_master_tracker()
            available_roles = get_roles_from_master_tracker()
        except Exception as e:
            logger.error(f"Could not load master tracker fields: {e}")
            master_tracker_fields = []
            available_trainings = []
            available_roles = []
            
        with st.form("access_request_form"):
            st.subheader("📝 Access Request Form")
            
            # Essential fields only
            col1, col2 = st.columns(2)
            
            with col1:
                user_id = st.text_input("Employee ID *", placeholder="EMP001", help="Enter your employee ID")
                name = st.text_input("Name *", placeholder="John Doe", help="Enter your full name")
                description = st.text_area("Description *", 
                    placeholder="Need access for managing customer accounts", 
                    height=100,
                    help="Describe why you need this access")
            
            with col2:
                # Get Role and Access Level from master tracker fields
                role = ""
                access_level = ""
                application_name = ""
                
                if master_tracker_fields:
                    # Find role field - use dropdown if roles available from Excel
                    role_field = next((f for f in master_tracker_fields if f['id'] == 'role'), None)
                    if role_field:
                        if available_roles:
                            role = st.selectbox(f"{role_field['label']} *", 
                                options=available_roles,
                                help=f"Select your role (from master tracker)")
                        else:
                            role = st.text_input(f"{role_field['label']} *", 
                                placeholder="e.g., Data Analyst", 
                                help=role_field.get('help_text', ''))
                    
                    # Find access level field
                    access_level_field = next((f for f in master_tracker_fields if f['id'] == 'access_level'), None)
                    if access_level_field:
                        options = access_level_field.get('options', ["Read-Only", "Read/Write", "Full", "Restricted"])
                        access_level = st.selectbox(f"{access_level_field['label']} *", 
                            options=options,
                            help=access_level_field.get('help_text', ''))
                    
                    # Find application name field
                    app_field = next((f for f in master_tracker_fields if f['id'] == 'application_name'), None)
                    if app_field:
                        application_name = st.text_input(f"{app_field['label']} *", 
                            placeholder="e.g., Medidata", 
                            help=app_field.get('help_text', ''))
                else:
                    # Fallback if no master tracker fields
                    if available_roles:
                        role = st.selectbox("Role *", options=available_roles)
                    else:
                        role = st.text_input("Role *", placeholder="e.g., Data Analyst")
                    access_level = st.selectbox("Access Level *", 
                        ["Read-Only", "Read/Write", "Full", "Restricted"])
                    application_name = st.text_input("Application Name *", placeholder="e.g., Medidata")
                
                # Training completed - fetch from master tracker
                trainings_completed = []
                if available_trainings:
                    trainings_completed = st.multiselect("Training Completed",
                        available_trainings,
                        help="Select all trainings you have completed (from master tracker)")
                else:
                    st.info("ℹ️ No trainings found in master tracker Excel file")
            
            submitted = st.form_submit_button("🚀 Submit Request", use_container_width=True)
                
            if submitted:
                # Build master tracker data from form fields
                master_tracker_data = {
                    "application_name": application_name,
                    "role": role,
                    "access_level": access_level
                }
                
                # Build requested permission string
                permission_parts = []
                if application_name:
                    permission_parts.append(application_name)
                if role:
                    permission_parts.append(role)
                if access_level:
                    permission_parts.append(f"({access_level})")
                
                requested_permission = " - ".join(permission_parts) if permission_parts else ""
                    
                # Validate required fields
                required_fields_ok = user_id and name and description and role and access_level and application_name
                
                if not required_fields_ok:
                    st.error("Please fill in all required fields (marked with *)")
                else:
                    with st.spinner("Processing request..."):
                        try:
                            # Determine request type based on application
                            request_type = "application_access"  # Default
                            
                            user_info = {
                                "username": name,  # Use username field instead of name
                                "role": role,
                                "context_data": {
                                    "name": name,  # Store name in context_data
                                    "completed_trainings": trainings_completed,
                                    "master_tracker_data": master_tracker_data
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
                                
                            # Handle ask_for_more_info decision
                            if result['decision'] == "ask_for_more_info":
                                st.warning("⚠️ **Additional Information Required**")
                                st.markdown("### 📝 Please provide the following information:")
                                    
                                # Extract missing info from reasoning
                                reasoning = result['reasoning']
                                if "Missing Information Required:" in reasoning:
                                    missing_info = reasoning.split("Missing Information Required:")[1].strip()
                                    missing_items = [item.strip() for item in missing_info.split(",")]
                                        
                                    st.markdown("The AI needs the following information to make a decision:")
                                    for item in missing_items:
                                        st.markdown(f"- {item}")
                                        
                                    st.info("Please update your request with the missing information and resubmit.")
                            else:
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
    
    elif page == "💬 AI Assistant":
        st.markdown('<h1 class="main-header">💬 AI Assistant</h1>', unsafe_allow_html=True)
        st.markdown("Ask me anything about the UAM system, access management, or general questions!")
        
        # Initialize chat client
        chat_client = initialize_chat_client()
        
        if not chat_client:
            st.warning("⚠️ OpenAI API key not configured. Please configure your API key in the .env file to use the AI Assistant.")
            st.info("💡 Add `OPENAI_API_KEY=your-key-here` to your .env file or configure Azure OpenAI settings.")
        else:
            # Display chat history
            st.markdown("### 💬 Conversation")
            
            # Initialize messages if empty (add system message)
            if len(st.session_state.chat_messages) == 0:
                st.session_state.chat_messages = [
                    {"role": "system", "content": get_chat_system_prompt()},
                    {"role": "assistant", "content": "Hello! I'm your UAM AI Assistant. How can I help you today? You can ask me about access management, permission rules, training requirements, or anything else related to the system."}
                ]
            
            # Display messages (skip system message)
            for msg in st.session_state.chat_messages:
                if msg["role"] == "system":
                    continue
                elif msg["role"] == "user":
                    with st.chat_message("user"):
                        st.write(msg["content"])
                elif msg["role"] == "assistant":
                    with st.chat_message("assistant"):
                        st.write(msg["content"])
            
            # Chat input
            user_input = st.chat_input("Type your message here...")
            
            if user_input:
                # Add user message to history
                st.session_state.chat_messages.append({"role": "user", "content": user_input})
                
                # Display user message immediately
                with st.chat_message("user"):
                    st.write(user_input)
                
                # Get AI response
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        try:
                            from config import USE_AZURE_OPENAI, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME, MODEL_NAME
                            
                            # Prepare messages (include system message)
                            messages_for_api = [
                                {"role": "system", "content": get_chat_system_prompt()}
                            ] + [
                                {"role": msg["role"], "content": msg["content"]}
                                for msg in st.session_state.chat_messages
                                if msg["role"] != "system"
                            ]
                            
                            model_or_deployment = AZURE_OPENAI_CHAT_DEPLOYMENT_NAME if USE_AZURE_OPENAI else MODEL_NAME
                            
                            response = chat_client.chat.completions.create(
                                model=model_or_deployment,
                                messages=messages_for_api,
                                temperature=0.7,
                                max_tokens=1000
                            )
                            
                            assistant_response = response.choices[0].message.content
                            
                            # Display and save assistant response
                            st.write(assistant_response)
                            st.session_state.chat_messages.append({"role": "assistant", "content": assistant_response})
                            st.rerun()  # Rerun to update the chat display
                            
                        except Exception as e:
                            error_msg = f"Sorry, I encountered an error: {str(e)}"
                            st.error(error_msg)
                            logger.error(f"Chat error: {e}")
                            st.session_state.chat_messages.append({"role": "assistant", "content": error_msg})
                            st.rerun()  # Rerun to update the chat display
            
            # Clear chat button
            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.chat_messages = [
                    {"role": "system", "content": get_chat_system_prompt()},
                    {"role": "assistant", "content": "Hello! I'm your UAM AI Assistant. How can I help you today? You can ask me about access management, permission rules, training requirements, or anything else related to the system."}
                ]
                st.rerun()
        
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
        

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6c757d;'>
    UAM Agentic AI System | Built with Streamlit
</div>
""", unsafe_allow_html=True)

