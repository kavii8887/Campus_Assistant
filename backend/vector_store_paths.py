"""
Vector Store Path Manager - Department-Scoped Collections
==========================================================
Manages vector DB directory structure for Phase 3.

Structure:
    vector_db/
    ├── global/
    │   └── regulation/
    ├── CSE/
    │   ├── syllabus/
    │   ├── timetable/
    │   ├── attendance/
    │   └── staff/
    └── [other departments...]

Version: 1.0
"""

from pathlib import Path
from typing import Optional


class VectorStorePaths:
    """
    Manages department-scoped vector store paths.
    
    CRITICAL RULES:
    - Each department gets own folder
    - Each data type gets own collection
    - NO shared collections between departments
    - Regulation is global (one only)
    """
    
    VALID_DEPARTMENTS = {'CSE', 'ECE', 'EEE', 'MECH', 'CIVIL'}
    VALID_DATA_TYPES = {'syllabus', 'timetable', 'attendance', 'staff'}
    
    def __init__(self, base_path: str = "./vector_db"):
        self.base_path = Path(base_path)
        self._ensure_structure()
    
    def _ensure_structure(self):
        """Create directory structure if it doesn't exist."""
        # Global regulation path
        (self.base_path / "global" / "regulation").mkdir(parents=True, exist_ok=True)
        
        # Department paths
        for dept in self.VALID_DEPARTMENTS:
            for data_type in self.VALID_DATA_TYPES:
                (self.base_path / dept / data_type).mkdir(parents=True, exist_ok=True)
    
    def get_collection_name(
        self,
        data_type: str,
        department: Optional[str] = None
    ) -> str:
        """
        Get collection name for a data type.
        
        Args:
            data_type: 'syllabus', 'timetable', 'attendance', 'staff', 'regulation'
            department: Department code (required except for regulation)
            
        Returns:
            Collection name string
        """
        if data_type == 'regulation':
            return "regulation_global"
        
        if not department:
            raise ValueError(f"Department required for data_type: {data_type}")
        
        department = department.upper()
        if department not in self.VALID_DEPARTMENTS:
            raise ValueError(f"Invalid department: {department}. Valid: {self.VALID_DEPARTMENTS}")
        
        if data_type not in self.VALID_DATA_TYPES:
            raise ValueError(f"Invalid data_type: {data_type}. Valid: {self.VALID_DATA_TYPES}")
        
        return f"{department}_{data_type}"
    
    def get_persist_path(
        self,
        data_type: str,
        department: Optional[str] = None
    ) -> str:
        """
        Get persist path for a collection.
        
        Args:
            data_type: 'syllabus', 'timetable', 'attendance', 'staff', 'regulation'
            department: Department code (required except for regulation)
            
        Returns:
            Path string
        """
        if data_type == 'regulation':
            return str(self.base_path / "global" / "regulation")
        
        if not department:
            raise ValueError(f"Department required for data_type: {data_type}")
        
        department = department.upper()
        if department not in self.VALID_DEPARTMENTS:
            raise ValueError(f"Invalid department: {department}")
        
        if data_type not in self.VALID_DATA_TYPES:
            raise ValueError(f"Invalid data_type: {data_type}")
        
        return str(self.base_path / department / data_type)
    
    def list_collections(self, department: Optional[str] = None) -> list:
        """List all collections for a department or globally."""
        collections = []
        
        if department:
            department = department.upper()
            for data_type in self.VALID_DATA_TYPES:
                collections.append(self.get_collection_name(data_type, department))
        else:
            # List all collections
            collections.append("regulation_global")
            for dept in self.VALID_DEPARTMENTS:
                for data_type in self.VALID_DATA_TYPES:
                    collections.append(self.get_collection_name(data_type, dept))
        
        return collections