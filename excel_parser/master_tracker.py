"""Excel Master Tracker Parser"""
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from utils.logger import logger
from config import MASTER_TRACKER_PATH
from database.models import PermissionRule, get_db_session

class MasterTrackerParser:
    """Parses Excel master tracker for permission rules and pre-requisites"""
    
    def __init__(self, excel_path: Optional[Path] = None):
        self.excel_path = excel_path or MASTER_TRACKER_PATH
        self.data = None
        
    def load_excel(self) -> pd.DataFrame:
        """Load Excel file into DataFrame"""
        try:
            if not self.excel_path.exists():
                logger.warning(f"Master tracker not found at {self.excel_path}. Creating sample structure.")
                self._create_sample_excel()
            
            # Try to read the first sheet (or specify sheet name)
            self.data = pd.read_excel(self.excel_path, sheet_name=0)
            logger.info(f"Loaded master tracker with {len(self.data)} rows")
            return self.data
        except Exception as e:
            logger.error(f"Error loading Excel file: {e}")
            raise
    
    def parse_permission_rules(self) -> List[Dict]:
        """
        Parse Excel data into permission rules structure.
        
        Expected Excel columns:
        - Permission_Type: Type of permission (e.g., Application Access)
        - Permission_Name: Specific permission name
        - Pre_Requisites: Comma-separated or JSON list of requirements
        - Criteria: Conditions that must be met
        - Priority_Level: high/medium/low
        - Auto_Grant: yes/no or true/false
        """
        if self.data is None:
            self.load_excel()
        
        rules = []
        
        # Normalize column names (handle variations)
        columns = {col.lower().replace(' ', '_').replace('-', '_'): col 
                  for col in self.data.columns}
        
        for _, row in self.data.iterrows():
            try:
                rule = {
                    "permission_type": self._get_value(row, columns, ['permission_type', 'type']),
                    "permission_name": self._get_value(row, columns, ['permission_name', 'name', 'permission']),
                    "pre_requisites": self._parse_json_or_list(self._get_value(row, columns, ['pre_requisites', 'prerequisites', 'pre_requisite'])),
                    "criteria": self._parse_json_or_list(self._get_value(row, columns, ['criteria', 'granting_criteria'])),
                    "priority_level": self._get_value(row, columns, ['priority_level', 'priority'], default="medium"),
                    "auto_grant_enabled": self._parse_boolean(self._get_value(row, columns, ['auto_grant', 'auto_grant_enabled'])),
                }
                
                if rule["permission_type"]:  # Only add if has permission type
                    rules.append(rule)
            except Exception as e:
                logger.warning(f"Error parsing row {_}: {e}")
                continue
        
        logger.info(f"Parsed {len(rules)} permission rules")
        return rules
    
    def _get_value(self, row, columns, possible_keys: List[str], default=None):
        """Get value from row using possible column name variations"""
        for key in possible_keys:
            if key in columns:
                value = row[columns[key]]
                if pd.notna(value):
                    return value
        return default
    
    def _parse_json_or_list(self, value) -> List:
        """Parse value that might be JSON string, comma-separated, or list"""
        if pd.isna(value) or value is None:
            return []
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, str):
            # Try JSON first
            try:
                import json
                return json.loads(value)
            except:
                # Try comma-separated
                return [item.strip() for item in value.split(',') if item.strip()]
        
        return []
    
    def _parse_boolean(self, value) -> bool:
        """Parse boolean from various formats"""
        if pd.isna(value) or value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['yes', 'true', '1', 'y', 'enabled']
        return bool(value)
    
    def sync_to_database(self):
        """Sync parsed rules to database"""
        rules = self.parse_permission_rules()
        db = get_db_session()
        
        try:
            # Clear existing rules (or implement update logic)
            db.query(PermissionRule).delete()
            
            for rule_data in rules:
                rule = PermissionRule(**rule_data)
                db.add(rule)
            
            db.commit()
            logger.info(f"Synced {len(rules)} rules to database")
        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing to database: {e}")
            raise
        finally:
            db.close()
    
    def _create_sample_excel(self):
        """Create sample Excel structure if file doesn't exist"""
        sample_data = {
            "Permission_Type": [
                "Application Access",
                "Application Access",
                "System Access",
                "Database Access"
            ],
            "Permission_Name": [
                "Salesforce Access",
                "ServiceNow Access",
                "Linux Server Access",
                "Production DB Read Access"
            ],
            "Pre_Requisites": [
                "Valid Employee ID, Department Approval, Security Training",
                "Valid Employee ID, Manager Approval",
                "Valid Employee ID, IT Department, Security Clearance, Manager Approval",
                "Valid Employee ID, Database Training, Manager Approval, Security Clearance"
            ],
            "Criteria": [
                "Department matches, Role matches, No security violations",
                "Department matches, Active employee",
                "IT role, Security clearance level 2+, Manager approval",
                "DBA role or Developer role, Completed training, Manager approval"
            ],
            "Priority_Level": [
                "medium",
                "medium",
                "high",
                "high"
            ],
            "Auto_Grant": [
                "yes",
                "yes",
                "no",
                "no"
            ]
        }
        
        df = pd.DataFrame(sample_data)
        df.to_excel(self.excel_path, index=False)
        logger.info(f"Created sample master tracker at {self.excel_path}")

