"""
Session Manager - Conversation State (PHASE 4 UPDATE)
======================================================
Manages session context for multi-turn conversations.

PHASE 4 ADDITIONS:
- register_no: Student register number
- student_year: Student year (1-4)
- student_semester: Student semester (odd/even)
- student_department: Student department code

CRITICAL RULES:
- Stores ONLY identifiers (codes, units, student metadata)
- NEVER stores knowledge or answers
- Expires after inactivity
- Resets unit when course changes

Version: 1.4 (Phase 4: Attendance metadata)
"""

import time
import uuid
from typing import Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class SessionState:
    """
    Session state for conversation continuity.
    
    PHASE 4: Added student metadata for attendance queries.
    """
    session_id: str
    active_course_code: Optional[str] = None
    active_course_name: Optional[str] = None
    active_unit: Optional[str] = None
    active_department: Optional[str] = None
    last_activity: float = field(default_factory=time.time)
    
    # PHASE 4: Student metadata for attendance
    register_no: Optional[str] = None
    student_year: Optional[int] = None
    student_semester: Optional[str] = None  # 'odd' or 'even'
    student_department: Optional[str] = None
    
    def is_expired(self, timeout: int) -> bool:
        """Check if session has expired."""
        return (time.time() - self.last_activity) > timeout
    
    def update_unit(self, unit: str):
        """Update active unit."""
        self.active_unit = unit
        self.last_activity = time.time()
    
    def reset_unit(self):
        """Clear active unit."""
        self.active_unit = None
        self.last_activity = time.time()


class SessionManager:
    """
    In-memory session storage for conversation continuity.
    
    PHASE 4: Enhanced with student metadata for attendance queries.
    
    Session contains:
    - active_course_code (CRITICAL: Must persist across queries)
    - active_course_name
    - active_unit
    - active_department
    - last_activity timestamp
    - clarification_state (for option selection)
    - register_no (student register number)
    - student_year (1-4)
    - student_semester (odd/even)
    - student_department (CSE, ECE, etc.)
    
    Session does NOT contain:
    - Generated answers
    - Retrieved content
    - Inferred facts
    """
    
    def __init__(self, default_timeout: int = 1800):
        """
        Args:
            default_timeout: Session expiry in seconds (default 30 min)
        """
        self.sessions: Dict[str, SessionState] = {}
        self.default_timeout = default_timeout
        self.clarification_state: Dict[str, Dict] = {}
    
    def create_session(
        self,
        register_no: Optional[str] = None,
        student_year: Optional[int] = None,
        student_semester: Optional[str] = None,
        student_department: Optional[str] = None,
    ) -> SessionState:
        """
        Create new session with optional student metadata.
        
        PHASE 4: Accepts student metadata for attendance queries.
        """
        session_id = str(uuid.uuid4())
        session = SessionState(
            session_id=session_id,
            last_activity=time.time(),
            register_no=register_no,
            student_year=student_year,
            student_semester=student_semester,
            student_department=student_department,
        )
        self.sessions[session_id] = session
        return session
    
    def peek_session(self, session_id: str) -> Optional[SessionState]:
        """
        Non-mutating session read.
        Get session WITHOUT updating timestamp.
        Use this for reading state without committing changes.
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check expiry but don't update timestamp
        if session.is_expired(self.default_timeout):
            return None
        
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        """
        Get existing session and update activity timestamp.
        Returns None if expired or not found.
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check expiry
        if session.is_expired(self.default_timeout):
            del self.sessions[session_id]
            if session_id in self.clarification_state:
                del self.clarification_state[session_id]
            return None
        
        # Update activity timestamp
        session.last_activity = time.time()
        return session
    
    def update_session(
        self,
        session_id: str,
        course_code: Optional[str] = None,
        course_name: Optional[str] = None,
        unit: Optional[str] = None,
        reset_unit: bool = False,
        register_no: Optional[str] = None,
        student_year: Optional[int] = None,
        student_semester: Optional[str] = None,
        student_department: Optional[str] = None,
    ):
        """
        Update session state.
        
        PHASE 4: Added student metadata parameters.
        
        CRITICAL: When course changes, unit is reset automatically.
        """
        # Use mutating get_session to ensure session exists and is active
        session = self.get_session(session_id)
        if not session:
            # Session expired or doesn't exist - cannot update
            return
        
        # Store previous course to detect changes
        previous_course = session.active_course_code
        
        # Update course (CRITICAL: This must persist)
        if course_code is not None:
            # Always update the course code
            session.active_course_code = course_code
            
            # Update course name if provided
            if course_name is not None:
                session.active_course_name = course_name
            
            # Reset unit only if course actually changed
            if previous_course is not None and course_code != previous_course:
                session.active_unit = None
        
        # BLOCKER - never set unit without course
        # Prevents orphaned unit state that could mislead retrieval
        if unit is not None:
            if session.active_course_code is None:
                # Guard: refuse to set unit when no course is active
                return
            session.update_unit(unit)
        
        if reset_unit:
            session.reset_unit()
        
        # PHASE 4: Update student metadata
        if register_no is not None:
            session.register_no = register_no
        if student_year is not None:
            session.student_year = student_year
        if student_semester is not None:
            session.student_semester = student_semester.lower()
        if student_department is not None:
            session.student_department = student_department.upper()
        
        # Ensure activity timestamp is current
        session.last_activity = time.time()
    
    def get_active_course(self, session_id: str) -> Optional[str]:
        """Get active course code from session."""
        session = self.peek_session(session_id)
        return session.active_course_code if session else None
    
    def get_active_unit(self, session_id: str) -> Optional[str]:
        """Get active unit from session."""
        session = self.peek_session(session_id)
        return session.active_unit if session else None
    
    def delete_session(self, session_id: str):
        """Delete session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.clarification_state:
            del self.clarification_state[session_id]
    
    def cleanup_expired(self):
        """Remove all expired sessions."""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.default_timeout)
        ]
        
        for sid in expired:
            del self.sessions[sid]
            if sid in self.clarification_state:
                del self.clarification_state[sid]
        
        return len(expired)
    
    def get_session_info(self, session_id: str) -> Optional[str]:
        """Get session info for debugging."""
        session = self.peek_session(session_id)
        if not session:
            return "No active session"
        
        info = f"Session: {session.session_id[:8]}...\n"
        info += f"Course: {session.active_course_code or 'None'}"
        if session.active_course_name:
            info += f" ({session.active_course_name})"
        info += f"\nUnit: {session.active_unit or 'None'}"
        info += f"\nDepartment: {session.active_department or 'None'}"
        
        # PHASE 4: Student metadata
        if session.register_no:
            info += f"\nStudent: {session.register_no}"
            if session.student_year:
                info += f" (Year {session.student_year}"
                if session.student_semester:
                    info += f", {session.student_semester.upper()}"
                info += ")"
        
        info += f"\nLast activity: {int(time.time() - session.last_activity)}s ago"
        
        if session_id in self.clarification_state:
            info += "\nPending clarification: Yes"
        
        return info
    
    def set_clarification(
        self,
        session_id: str,
        options: List[str],
        original_query: str
    ):
        """Store clarification options for follow-up."""
        self.clarification_state[session_id] = {
            'options': options,
            'original_query': original_query,
            'timestamp': time.time()
        }
    
    def get_clarification(self, session_id: str) -> Optional[Dict]:
        """Get pending clarification state."""
        return self.clarification_state.get(session_id)
    
    def clear_clarification(self, session_id: str):
        """Clear clarification state after resolution."""
        if session_id in self.clarification_state:
            del self.clarification_state[session_id]