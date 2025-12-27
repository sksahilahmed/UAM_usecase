"""Utility to extract form fields from master tracker Excel"""
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from config import MASTER_TRACKER_PATH
from utils.logger import logger

def get_master_tracker_form_fields() -> List[Dict]:
    """
    Extract form fields from master tracker Excel file
    Returns list of field definitions for UI forms
    """
    if not MASTER_TRACKER_PATH.exists():
        logger.warning(f"Master tracker not found at {MASTER_TRACKER_PATH}")
        return []
    
    try:
        df = pd.read_excel(MASTER_TRACKER_PATH, sheet_name=0)
        
        # Get header row (row 0)
        headers = {}
        for col in df.columns:
            # Check first row value (actual header)
            if len(df) > 0:
                header_value = df.iloc[0][col]
                if pd.notna(header_value) and str(header_value).strip():
                    headers[col] = str(header_value).strip()
        
        # Map to form fields
        form_fields = []
        
        # Application Name / Access requirement
        app_col = None
        for col in df.columns:
            if 'access requirement' in str(col).lower() or 'application' in str(headers.get(col, '')).lower():
                app_col = col
                break
        
        if app_col:
            form_fields.append({
                "id": "application_name",
                "label": headers.get(app_col, "Application Name"),
                "type": "text",
                "required": True,
                "help_text": "Name of the application or system",
                "column": app_col
            })
        
        # Role
        role_col = None
        for col in df.columns:
            if 'role' in str(headers.get(col, '')).lower():
                role_col = col
                break
        
        if role_col:
            form_fields.append({
                "id": "role",
                "label": headers.get(role_col, "Role"),
                "type": "text",
                "required": True,
                "help_text": "Specific role or permission level",
                "column": role_col
            })
        
        # Access Level
        access_level_col = None
        for col in df.columns:
            if 'access level' in str(headers.get(col, '')).lower():
                access_level_col = col
                break
        
        if access_level_col:
            form_fields.append({
                "id": "access_level",
                "label": headers.get(access_level_col, "Access Level"),
                "type": "select",
                "options": ["Read-Only", "Read/Write", "Full", "Restricted"],
                "required": True,
                "help_text": "Level of access required",
                "column": access_level_col
            })
        
        # Environment
        env_col = None
        for col in df.columns:
            if 'environment' in str(headers.get(col, '')).lower():
                env_col = col
                break
        
        if env_col:
            form_fields.append({
                "id": "environment",
                "label": headers.get(env_col, "Environment"),
                "type": "select",
                "options": ["Prod", "QA", "Dev", "Test"],
                "required": True,
                "help_text": "Target environment",
                "column": env_col
            })
        
        # Training Required (for display/validation)
        training_col = None
        for col in df.columns:
            if 'training' in str(headers.get(col, '')).lower() or 'pre-requisite' in str(headers.get(col, '')).lower():
                training_col = col
                break
        
        if training_col:
            form_fields.append({
                "id": "training_required",
                "label": headers.get(training_col, "Training Required"),
                "type": "info",
                "required": False,
                "help_text": "Training requirements for this access (will be validated)",
                "column": training_col
            })
        
        # Approval Required
        approval_col = None
        for col in df.columns:
            if 'approval' in str(headers.get(col, '')).lower():
                approval_col = col
                break
        
        if approval_col:
            form_fields.append({
                "id": "approval_required",
                "label": headers.get(approval_col, "Approval Required"),
                "type": "text",
                "required": False,
                "help_text": "Type of approval needed (e.g., Line manager, System owner)",
                "column": approval_col
            })
        
        # Authorizing Manager
        manager_col = None
        for col in df.columns:
            if 'manager' in str(headers.get(col, '')).lower() or 'authorizing' in str(headers.get(col, '')).lower():
                manager_col = col
                break
        
        if manager_col:
            form_fields.append({
                "id": "authorizing_manager",
                "label": headers.get(manager_col, "Authorizing Manager"),
                "type": "text",
                "required": False,
                "help_text": "Name of the authorizing manager",
                "column": manager_col
            })
        
        # Exception Scenario (for display)
        exception_col = None
        for col in df.columns:
            if 'exception' in str(headers.get(col, '')).lower() or 'provisioning' in str(col).lower():
                exception_col = col
                break
        
        if exception_col:
            form_fields.append({
                "id": "exception_scenario",
                "label": headers.get(exception_col, "Exception Scenario"),
                "type": "info",
                "required": False,
                "help_text": "Special restrictions or exceptions (e.g., not for contractors)",
                "column": exception_col
            })
        
        # Notes
        notes_col = None
        for col in df.columns:
            if 'note' in str(headers.get(col, '')).lower() and 'unnamed' not in str(col).lower():
                notes_col = col
                break
        
        if notes_col:
            form_fields.append({
                "id": "notes",
                "label": headers.get(notes_col, "Notes"),
                "type": "textarea",
                "required": False,
                "help_text": "Additional notes or special requirements",
                "column": notes_col
            })
        
        logger.info(f"Extracted {len(form_fields)} form fields from master tracker")
        return form_fields
        
    except Exception as e:
        logger.error(f"Error extracting form fields from master tracker: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []

def get_roles_from_master_tracker() -> List[str]:
    """
    Extract unique roles from master tracker Excel file
    Returns list of role names
    """
    if not MASTER_TRACKER_PATH.exists():
        logger.warning(f"Master tracker not found at {MASTER_TRACKER_PATH}")
        return []
    
    try:
        df = pd.read_excel(MASTER_TRACKER_PATH, sheet_name=0)
        
        # Find role column - check both column name and header row value
        role_col = None
        headers = {}
        
        # First, get header row values (row 0)
        for col in df.columns:
            if len(df) > 0:
                header_value = df.iloc[0][col]
                if pd.notna(header_value):
                    headers[col] = str(header_value).strip()
        
        # Find column with role in name or header
        for col in df.columns:
            col_str = str(col).lower()
            header_str = str(headers.get(col, '')).lower()
            if 'role' in col_str or 'role' in header_str:
                role_col = col
                break
        
        if not role_col:
            logger.warning("Role column not found in master tracker")
            return []
        
        # Get all role values from the column (skip header row)
        roles = set()
        for idx in range(1, len(df)):  # Skip header row (row 0)
            value = df.iloc[idx][role_col]
            if pd.notna(value):
                role_str = str(value).strip()
                if role_str and len(role_str) > 1:  # Filter out very short strings
                    roles.add(role_str)
        
        result = sorted(list(roles))
        logger.info(f"Extracted {len(result)} unique roles from master tracker")
        return result
    except Exception as e:
        logger.error(f"Error extracting roles from master tracker: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []

def get_trainings_from_master_tracker() -> List[str]:
    """
    Extract unique training requirements from master tracker Excel file
    Returns list of training names
    """
    if not MASTER_TRACKER_PATH.exists():
        logger.warning(f"Master tracker not found at {MASTER_TRACKER_PATH}")
        return []
    
    try:
        df = pd.read_excel(MASTER_TRACKER_PATH, sheet_name=0)
        
        # Find training column - check both column name and header row value
        training_col = None
        headers = {}
        
        # First, get header row values (row 0)
        for col in df.columns:
            if len(df) > 0:
                header_value = df.iloc[0][col]
                if pd.notna(header_value):
                    headers[col] = str(header_value).strip()
        
        # Find column with training in name or header
        for col in df.columns:
            col_str = str(col).lower()
            header_str = str(headers.get(col, '')).lower()
            if 'training' in col_str or 'pre-requisite' in col_str or 'prerequisite' in col_str or \
               'training' in header_str or 'pre-requisite' in header_str or 'prerequisite' in header_str:
                training_col = col
                break
        
        if not training_col:
            logger.warning("Training column not found in master tracker")
            return []
        
        # Get all training values from the column (skip header row)
        trainings = set()
        for idx in range(1, len(df)):  # Skip header row (row 0)
            value = df.iloc[idx][training_col]
            if pd.notna(value):
                # Split by comma and clean up
                training_str = str(value)
                training_list = training_str.split(',')
                for training in training_list:
                    training = training.strip()
                    if training and len(training) > 2:  # Filter out very short strings
                        trainings.add(training)
        
        result = sorted(list(trainings))
        logger.info(f"Extracted {len(result)} unique trainings from master tracker")
        return result
    except Exception as e:
        logger.error(f"Error extracting trainings from master tracker: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []

def get_master_tracker_field_values(requested_permission: str) -> Dict:
    """
    Get field values from master tracker for a specific permission
    Returns dict of field_id: value
    """
    if not MASTER_TRACKER_PATH.exists():
        return {}
    
    try:
        df = pd.read_excel(MASTER_TRACKER_PATH, sheet_name=0)
        fields = get_master_tracker_form_fields()
        
        # Find matching row
        for idx in range(1, len(df)):  # Skip header
            row = df.iloc[idx]
            
            # Check if this row matches
            for field in fields:
                col = field.get('column')
                if col and pd.notna(row[col]):
                    value = str(row[col])
                    # Simple matching - check if permission contains role or app name
                    if field['id'] == 'role' and any(word in requested_permission.lower() for word in value.lower().split() if len(word) > 3):
                        # Found matching row, return all values
                        result = {}
                        for f in fields:
                            col_name = f.get('column')
                            if col_name and pd.notna(row[col_name]):
                                result[f['id']] = str(row[col_name])
                        return result
        
        return {}
    except Exception as e:
        logger.error(f"Error getting field values: {e}")
        return {}

