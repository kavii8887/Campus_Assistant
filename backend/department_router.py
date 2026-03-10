"""
department_router.py — Department-scoped resource management
=============================================================
Handles:
  - Discovering available departments from disk
  - Loading / caching CourseCodeResolver per department
  - Loading / caching SemanticVectorStore per department (syllabus)
  - Loading / caching SemanticVectorStore per department (attendance) ← PHASE 4
  - Loading / caching StructuredAcademicStore per department
  - Session-department association
  - set_department() API
  - Timetable structured directory management ← PHASE 5

Version: 1.2 (Phase 5: Textract Timetable)
"""


from pathlib import Path
from typing import Dict, List, Optional, Any

from vector_store_paths import VectorStorePaths

# ── Module-level caches (survive department switches within a process) ─────────
_resolver_cache: Dict[str, Any] = {}
_vector_cache: Dict[str, Any] = {}
_attendance_cache: Dict[str, Any] = {}  # PHASE 4: Attendance vector stores
_struct_cache: Dict[str, Any] = {}   # StructuredAcademicStore per dept


class DepartmentRouter:
    """
    Manages per-department resources and exposes set_department() API.

    Designed to be composed into AcademicRAGSystem; not a standalone service.
    
    PHASE 5: Ensures timetable/structured directory for Textract ingestion.
    """

    def __init__(self, persist_path: str, ollama):
        self.persist_path = persist_path
        self.ollama = ollama

        # Active department (legacy / instance-level state)
        self.department: Optional[str] = None

        # Pointers to active resources (swapped on department change)
        self.course_resolver = None
        self.vector_db = None
        self.attendance_db = None  # PHASE 4: Attendance vector store
        self.structured_store = None
        
        # PHASE 5: Ensure structured timetable directories exist
        self._ensure_timetable_structured_dirs()

    # ── Discovery ─────────────────────────────────────────────────────────────

    def get_available_departments(self) -> List[str]:
        """
        Return department codes discovered from disk.
        A department exists if <persist_path>/<DEPT>/syllabus/ is a directory.
        """
        base = Path(self.persist_path)
        if not base.exists():
            return []
        return [
            child.name.upper()
            for child in sorted(base.iterdir())
            if child.is_dir() and (child / "syllabus").is_dir()
        ]
    
    def _ensure_timetable_structured_dirs(self):
        """
        PHASE 5: Ensure timetable/structured directories exist for all departments.
        Called during initialization to support Textract ingestion.
        """
        base = Path(self.persist_path)
        
        try:
            paths = VectorStorePaths(self.persist_path)
            
            for dept in paths.VALID_DEPARTMENTS:
                timetable_structured = base / dept / "timetable" / "structured"
                timetable_structured.mkdir(parents=True, exist_ok=True)
        
        except Exception as e:
            print(f"⚠ Failed to create timetable/structured directories: {e}")

    # ── Resource initialisation ───────────────────────────────────────────────

    def init_department_resources(self, dept_code: str) -> None:
        """
        Load (or swap from cache) all resources for dept_code.
        Safe to call multiple times — cached after first load.
        Does NOT touch session state.
        """
        dept = dept_code.upper()

        # ── CourseCodeResolver ────────────────────────────────────────────────
        if dept not in _resolver_cache:
            from course_resolver import CourseCodeResolver
            resolver = CourseCodeResolver(department=dept)

            mapping_file = Path(f"data/{dept}/{dept}_course_mappings.txt")
            if not mapping_file.exists():
                mapping_file = Path("data/general/course_mappings.txt")
            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    resolver.load_mappings(f.read())

            # v5.x: acronym loading moved into course mappings / synonym system
            acronym_path = Path(f"data/{dept}/{dept}_acronyms.json")
            if acronym_path.exists() and hasattr(resolver, "load_acronyms"):
                resolver.load_acronyms(acronym_path)

            _resolver_cache[dept] = resolver
            print(f"✓ Resolver initialised for {dept}")
        else:
            print(f"✓ Resolver loaded from cache for {dept}")

        # ── SemanticVectorStore (Syllabus) ────────────────────────────────────
        if dept not in _vector_cache:
            from semantic_vector_store import SemanticVectorStore

            try:
                paths = VectorStorePaths(self.persist_path)
                collection_name = paths.get_collection_name("syllabus", dept)
                dept_vector_path = paths.get_persist_path("syllabus", dept)
            except Exception:
                # Legacy fallback if VectorStorePaths not available
                dept_vector_path = Path(self.persist_path) / dept / "syllabus"
                collection_name = f"{dept}_syllabus"

            embedding_dim = self.ollama.get_embedding_dim()
            vdb = SemanticVectorStore(
                collection_name=collection_name,
                embedding_dim=embedding_dim,
                persist_path=str(dept_vector_path)
            )
            _vector_cache[dept] = vdb
            print(f"✓ Vector DB initialised for {dept} ({collection_name})")
        else:
            print(f"✓ Vector DB loaded from cache for {dept}")

        # ── SemanticVectorStore (Attendance) PHASE 4 ──────────────────────────
        if dept not in _attendance_cache:
            from semantic_vector_store import SemanticVectorStore

            try:
                paths = VectorStorePaths(self.persist_path)
                collection_name = paths.get_collection_name("attendance", dept)
                attendance_path = paths.get_persist_path("attendance", dept)
            except Exception:
                # Fallback
                attendance_path = Path(self.persist_path) / dept / "attendance"
                collection_name = f"{dept}_attendance"

            embedding_dim = self.ollama.get_embedding_dim()
            attendance_db = SemanticVectorStore(
                collection_name=collection_name,
                embedding_dim=embedding_dim,
                persist_path=str(attendance_path)
            )
            _attendance_cache[dept] = attendance_db
            print(f"✓ Attendance DB initialised for {dept} ({collection_name})")
        else:
            print(f"✓ Attendance DB loaded from cache for {dept}")

        # ── StructuredAcademicStore ───────────────────────────────────────────
        if dept not in _struct_cache:
            try:
                from structured_store import StructuredAcademicStore
                struct_path = Path(self.persist_path) / dept / "structured"
                store = StructuredAcademicStore(persist_path=str(struct_path))
                _struct_cache[dept] = store
                print(f"✓ StructuredAcademicStore initialised for {dept}")
            except ImportError:
                _struct_cache[dept] = None
                print(f"⚠ StructuredAcademicStore not available — structured queries degraded")
            except Exception as e:
                _struct_cache[dept] = None
                print(f"⚠ StructuredAcademicStore failed to load for {dept}: {e}")
        else:
            print(f"✓ StructuredAcademicStore loaded from cache for {dept}")

        # Point instance attributes to active dept
        self.course_resolver = _resolver_cache[dept]
        self.vector_db = _vector_cache[dept]
        self.attendance_db = _attendance_cache[dept]  # PHASE 4
        self.structured_store = _struct_cache[dept]
        self.department = dept

    # ── set_department() API ──────────────────────────────────────────────────

    def set_department(
        self,
        dept_code: str,
        session_id: Optional[str],
        session_manager,
        last_course_code_ref: list,  # [str] — mutable single-element list for legacy state
    ) -> Dict[str, Any]:
        """
        Validate, initialise, and activate a department for a session.

        Args:
            dept_code:           Department code (case-insensitive).
            session_id:          Session to update (None → legacy instance mode).
            session_manager:     SessionManager instance (may be None).
            last_course_code_ref: [legacy_code] mutable ref so caller's state is cleared.

        Returns:
            {"ok": True, "department": dept_upper}  or  {"ok": False, "error": "..."}
        """
        dept = dept_code.strip().upper()
        available = self.get_available_departments()

        if available and dept not in available:
            return {
                "ok": False,
                "error": (
                    f"Department '{dept}' not found. "
                    f"Available: {', '.join(available) or 'none on disk'}"
                )
            }

        self.init_department_resources(dept)

        if session_id and session_manager:
            session = session_manager.get_session(session_id)
            if session and hasattr(session, 'active_department'):
                session.active_department = dept
                session.active_course_code = None
                session.active_course_name = None
                session.active_unit = None
        else:
            last_course_code_ref[0] = None   # clear legacy state

        print(f"✓ Department set to {dept}")
        return {"ok": True, "department": dept}

    # ── Session helpers ───────────────────────────────────────────────────────

    def get_session_department(
        self,
        session_id: Optional[str],
        session_manager,
    ) -> Optional[str]:
        """Return active department for session (or legacy instance dept)."""
        if session_id and session_manager:
            session = session_manager.peek_session(session_id)
            if session and hasattr(session, 'active_department'):
                return session.active_department
        return self.department

    def ensure_dept_resources(
        self,
        session_id: Optional[str],
        session_manager,
    ) -> Optional[str]:
        """
        Ensure instance resources match the session's active department.
        Returns dept code, or None if no department set.
        """
        dept = self.get_session_department(session_id, session_manager)
        if not dept:
            return None
        if dept != self.department or self.course_resolver is None:
            self.init_department_resources(dept)
        return dept