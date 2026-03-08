"""
runtime_engine.py — Query pipeline orchestrator
================================================
AcademicRAGSystem lives here.

Version: 1.7 (Final bug fixes: session persistence, conversational responses, all edge cases)
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from routing import (
    classify,
    QT_UNIT_CONTENT, QT_FULL_SYLLABUS, QT_FULL_SYLLABUS_MULTI,
    QT_COURSE_CODE, QT_COURSE_NAME, QT_CREDITS, QT_CREDITS_COMPARE,
    QT_OBJECTIVES, QT_OUTCOMES, QT_TEXTBOOKS, QT_REFERENCES,
    QT_LAB_EXERCISES, QT_UNIT_LIST,
    QT_ATTENDANCE_PERCENTAGE, QT_ATTENDANCE_STATUS, QT_ATTENDANCE_COUNT,
    STRUCTURED_STORE_TYPES, ATTENDANCE_TYPES, ALL_STRUCTURED_TYPES,
)
import structured_handlers as sh
import attendance_handlers as ah
from semantic_engine import SemanticEngine
from department_router import DepartmentRouter

try:
    from session_manager import SessionManager
    _SESSION_AVAILABLE = True
except ImportError:
    print("⚠ SessionManager not found - session persistence disabled")
    _SESSION_AVAILABLE = False
    SessionManager = None

# ── SessionState department patch ─────────────────────────────────────────────
if _SESSION_AVAILABLE:
    import session_manager as _sm
    if not hasattr(_sm.SessionState, 'active_department'):
        import dataclasses as _dc
        from typing import Optional as _Opt

        @_dc.dataclass
        class _PatchedState(_sm.SessionState):
            active_department: _Opt[str] = None

        _sm.SessionState = _PatchedState


class AcademicRAGSystem:
    """
    Production RAG system.
    Version 1.7: All bugs fixed - session persistence, conversational responses, metadata routing
    """

    def __init__(
        self,
        department: Optional[str] = None,
        persist_path: str = "./vector_db",
        max_context_chars: int = 1500,
        enable_sessions: bool = True,
        staff_json_path: Optional[str] = None,
    ):
        self.persist_path = persist_path
        self.last_course_code: Optional[str] = None
        self.last_course_name: Optional[str] = None
        self.last_ambiguities: List[Tuple[str, str]] = []

        self.session_manager = None
        if enable_sessions and _SESSION_AVAILABLE:
            self.session_manager = SessionManager(default_timeout=1800)
            print("✓ Session manager enabled (30 min timeout)")

        try:
            from ollama_client import OllamaClient
        except ImportError:
            import requests as _req

            class OllamaClient:
                def __init__(self, embedding_model="nomic-embed-text", llm_model="mistral:7b-instruct"):
                    self.embedding_model = embedding_model
                    self.llm_model = llm_model
                    self.embed_endpoint = "http://localhost:11434/api/embeddings"
                    self.generate_endpoint = "http://localhost:11434/api/generate"

                def embed_single(self, text):
                    r = _req.post(self.embed_endpoint, json={"model": self.embedding_model, "prompt": text})
                    return r.json()['embedding']

                def get_embedding_dim(self):
                    return len(self.embed_single("test"))

        self.ollama = OllamaClient(
            embedding_model="nomic-embed-text",
            llm_model="mistral:7b-instruct"
        )

        self._dept_router = DepartmentRouter(
            persist_path=persist_path,
            ollama=self.ollama,
        )

        self._semantic = SemanticEngine(
            ollama=self.ollama,
            max_context_chars=max_context_chars,
        )

        self.staff_data = self._load_staff_data(staff_json_path)

        print("=" * 70)
        print("ACADEMIC SYLLABUS RAG SYSTEM (v5.7 - ALL BUGS FIXED)")
        print("=" * 70)
        print(f"✓ Session persistence: FIXED")
        print(f"✓ Conversational responses: ENABLED")
        print(f"✓ Subject name synonym: ENABLED")
        print(f"✓ Metadata query routing: FIXED")
        print(f"✓ Max context: {max_context_chars} chars\n")

        if department:
            self._dept_router.init_department_resources(department)

    def _load_staff_data(self, json_path: Optional[str]) -> Optional[Dict]:
        if not json_path:
            json_path = "./staff_data.json"
        
        path = Path(json_path)
        if not path.exists():
            print(f"⚠ Staff data not found at {json_path}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✓ Loaded staff data: {len(data.get('staff', []))} records")
            return data
        except Exception as e:
            print(f"⚠ Failed to load staff data: {e}")
            return None

    @property
    def department(self) -> Optional[str]:
        return self._dept_router.department

    @property
    def course_resolver(self):
        return self._dept_router.course_resolver

    @property
    def vector_db(self):
        return self._dept_router.vector_db

    @property
    def structured_store(self):
        return self._dept_router.structured_store

    def get_available_departments(self) -> List[str]:
        return self._dept_router.get_available_departments()

    def set_department(self, dept_code: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        _legacy_ref = [self.last_course_code]
        result = self._dept_router.set_department(
            dept_code=dept_code,
            session_id=session_id,
            session_manager=self.session_manager,
            last_course_code_ref=_legacy_ref,
        )
        if result["ok"]:
            self.last_course_code = _legacy_ref[0]
            self.last_course_name = None
        return result

    def query(
        self,
        query_text: str,
        verbose: bool = True,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Main query pipeline."""

        # ── Bare course code detection ────────────────────────────────────────
        bare_code = self._is_bare_course_code(query_text)
        if bare_code:
            name = self.course_resolver.get_name_from_code(bare_code)
            if name:
                # BUG FIX 4: Update session for bare code queries too
                self.last_course_code = bare_code
                self.last_course_name = name
                if session_id and self.session_manager:
                    self.session_manager.update_session(session_id, course_code=bare_code, course_name=name)
                
                if verbose:
                    print(f"\n[BARE CODE] {bare_code} → {name}\n")
                return {
                    "query": query_text,
                    "answer": f"{bare_code} is {name}.",
                    "method": "bare_code",
                    "chunks_retrieved": 0,
                    "chunks_used": 0,
                    "llm_used": False,
                    "processing_time": 0.0
                }

        # ── Numeric disambiguation ────────────────────────────────────────────
        sel = self._is_numeric_selection(query_text)
        if sel is not None and self.last_ambiguities:
            code, name = self.last_ambiguities[sel - 1]
            self.last_course_code = code
            self.last_course_name = name
            if session_id and self.session_manager:
                self.session_manager.update_session(session_id, course_code=code, course_name=name)
            self.last_ambiguities = []
            if verbose:
                print(f"\n✓ Selected: {name} ({code})\n")
            return self.query(f"syllabus for {code}", verbose=verbose, session_id=session_id)

        # ── Semester block ────────────────────────────────────────────────────
        if self._is_semester_query(query_text):
            return self._blocked("Semester-level aggregate data is not available. Please ask about specific courses.")

        # ── DB status check ───────────────────────────────────────────────────
        session_course = self._get_session_course(session_id)
        is_structured, query_type = classify(query_text, session_course)

        if verbose:
            print(f"[CLASSIFICATION] is_structured={is_structured}, query_type={query_type or 'None'}")

        if query_type not in ATTENDANCE_TYPES:
            if not self._check_db_status():
                return self._blocked(
                    "No syllabus data ingested yet. Please run ingestion first.",
                    method="none"
                )

        if verbose:
            print("\n" + "=" * 70)
            print(f"QUERY: {query_text}")
            print("=" * 70 + "\n")

        # ── Department guard ──────────────────────────────────────────────────
        active_dept = self._dept_router.ensure_dept_resources(session_id, self.session_manager)
        if not active_dept:
            return self._blocked(
                "No department selected for this session. "
                "Please select a department first (e.g., call set_department('CSE'))."
            )

        is_lab_query = self._is_lab_query(query_text)

        # ── Unit extraction with validation ───────────────────────────────────
        unit_number, is_invalid_unit = self._extract_unit_number(query_text)
        if is_invalid_unit:
            return self._blocked(f"Unit {unit_number} doesn't exist. Valid units are: I, II, III, IV, V.")

        # ── Multi-course unit split ───────────────────────────────────────────
        if unit_number and re.search(r'\band\b', query_text, re.IGNORECASE):
            multi = self.course_resolver.resolve_multiple_codes(query_text)
            if len(multi) >= 2:
                if verbose:
                    print(f"[MULTI-COURSE UNIT] Splitting into {len(multi)} queries\n")
                results = []
                for code, name in multi:
                    sub = self.query(f"unit {unit_number} for {code}", verbose=False, session_id=session_id)
                    results.append(f"{'=' * 70}\n{name} ({code}):\n{'=' * 70}\n{sub['answer']}")
                return {
                    "query": query_text, "answer": "\n\n".join(results),
                    "method": "multi_course_unit", "chunks_retrieved": 0,
                    "chunks_used": 0, "llm_used": True, "processing_time": 1.0
                }

        # ── Course resolution pipeline ────────────────────────────────────────
        resolved_code, resolved_name = self._resolve_course(
            query_text, query_type, session_id, verbose
        )

        # Handle invalid explicit codes deterministically
        if resolved_code and not resolved_name and self._is_valid_code_format(resolved_code):
            return {
                "query": query_text,
                "answer": f"I don't have {resolved_code} in my database. Could you check the course code?",
                "method": "invalid_code",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.1
            }

        # Force structured routing when unit + course are both present
        if unit_number and resolved_code:
            is_structured = True
            query_type = QT_UNIT_CONTENT
            if verbose:
                print(f"[FORCE-STRUCTURED] unit={unit_number} + course={resolved_code} → UNIT_CONTENT\n")

        # Semantic follow-up: inherit session course
        if not resolved_code and not is_structured and not is_lab_query:
            if session_course:
                resolved_code = session_course
                resolved_name = self.course_resolver.get_name_from_code(session_course)
                if verbose:
                    print(f"[SESSION] Semantic follow-up → {resolved_name} ({resolved_code})\n")

        # Name consistency validation
        if resolved_code:
            actual_name = self.course_resolver.get_name_from_code(resolved_code)
            if actual_name and actual_name != resolved_name:
                if verbose:
                    print(f"[VALIDATION] Name corrected: {resolved_name} → {actual_name}")
                resolved_name = actual_name

        # Force structured routing if we have course + structured type
        if resolved_code and query_type and query_type in ALL_STRUCTURED_TYPES:
            if not is_structured:
                is_structured = True
                if verbose:
                    print(f"[FORCE-STRUCTURED] course={resolved_code} + type={query_type} → STRUCTURED\n")

        # ── BUG FIX 4: Update session for ALL queries (except comparisons) ────
        # This ensures "CCS342 subject name" updates session so "unit 1" works
        if resolved_code and query_type != QT_CREDITS_COMPARE:
            self.last_course_code = resolved_code
            self.last_course_name = resolved_name
            
            if session_id and self.session_manager:
                self.session_manager.update_session(
                    session_id=session_id,
                    course_code=resolved_code,
                    course_name=resolved_name,
                    unit=unit_number or None,
                )
                if verbose:
                    print(f"[SESSION UPDATE] {resolved_code} ({resolved_name}) → session\n")

        if verbose:
            self._log_resolution(active_dept, resolved_code, resolved_name,
                                 unit_number, query_type, is_structured, is_lab_query,
                                 session_id)

        # ── Structured lane ───────────────────────────────────────────────────
        if is_structured:
            if verbose:
                print(f"[ROUTING] STRUCTURED LANE (NO LLM)\n")

            answer = self._handle_structured(
                query_type,
                query_text,
                resolved_code,
                unit_number,
                session_id,
                verbose
            )

            # Restricted semantic fallback - only for content queries
            FALLBACK_ALLOWED_TYPES = {QT_UNIT_CONTENT, QT_FULL_SYLLABUS, QT_FULL_SYLLABUS_MULTI}
            if query_type in FALLBACK_ALLOWED_TYPES and answer.strip().lower() in {"not found.", "not in syllabus.", ""}:
                if verbose:
                    print(f"[FALLBACK] {query_type} returned weak answer → trying semantic reasoning\n")

                semantic = self._semantic.answer(
                    query=query_text,
                    course_code=resolved_code,
                    unit_number=unit_number,
                    vector_db=self.vector_db,
                    course_resolver=self.course_resolver,
                    is_lab_query=is_lab_query,
                    verbose=verbose,
                )

                if not semantic or not semantic.get("answer") or semantic["answer"].strip().lower() in {"not found.", "not in syllabus.", ""}:
                    semantic = {
                        "query": query_text,
                        "answer": (
                            "I couldn't find that in the syllabus. "
                            "Could you rephrase your question or ask about a specific unit?"
                        ),
                        "method": "semantic_fallback",
                        "chunks_retrieved": 0,
                        "chunks_used": 0,
                        "llm_used": True,
                        "processing_time": 0.2,
                    }
                return semantic
            
            return {
                "query": query_text,
                "answer": answer,
                "method": "structured",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.1
            }

        # ── Semantic lane ─────────────────────────────────────────────────────
        if verbose:
            print(f"[ROUTING] SEMANTIC LANE\n")
        return self._semantic.answer(
            query=query_text,
            course_code=resolved_code,
            unit_number=unit_number,
            vector_db=self.vector_db,
            course_resolver=self.course_resolver,
            is_lab_query=is_lab_query,
            verbose=verbose,
        )

    def _handle_structured(
        self,
        query_type: Optional[str],
        query: str,
        course_code: Optional[str],
        unit_number: Optional[str],
        session_id: Optional[str],
        verbose: bool,
    ) -> str:
        if verbose:
            print(f"  Query type: {query_type} (structured)")

        store = self.structured_store
        resolver = self.course_resolver

        if query_type in ATTENDANCE_TYPES:
            if verbose:
                print(f"  → Attendance handler (deterministic)\n")
            
            session = None
            if session_id and self.session_manager:
                session = self.session_manager.get_session(session_id)
            
            if not session:
                return "Attendance queries require an active session with student details. Please contact administrator."
            
            return ah.dispatch(
                query_type=query_type,
                session=session,
                router=self._dept_router,
                persist_path=self.persist_path
            )

        if query_type == "STAFF_INFO":
            if verbose:
                print(f"  → Staff info handler (deterministic)\n")
            
            session_course = None
            if session_id and self.session_manager:
                session_course = self.session_manager.get_active_course(session_id)
            elif self.last_course_code:
                session_course = self.last_course_code
            
            return sh.handle_staff_query(
                query, 
                course_code, 
                self.staff_data, 
                resolver,
                session_course=session_course
            )

        if query_type == QT_OBJECTIVES:
            return sh.handle_objectives(course_code, store)
        if query_type == QT_OUTCOMES:
            return sh.handle_outcomes(course_code, store)
        if query_type == QT_TEXTBOOKS:
            return sh.handle_textbooks(course_code, store)
        if query_type == QT_REFERENCES:
            return sh.handle_references(course_code, store)
        if query_type == QT_LAB_EXERCISES:
            return sh.handle_lab_exercises(course_code, store)
        if query_type == QT_UNIT_LIST:
            return sh.handle_unit_list(course_code, store)

        if query_type == QT_CREDITS:
            return sh.handle_credits(course_code, resolver)
        if query_type == QT_COURSE_NAME:
            return sh.handle_course_name(course_code, resolver)
        if query_type == QT_COURSE_CODE:
            answer, new_ambs = sh.handle_course_code(
                course_code, self.last_course_name, resolver, query, self.last_ambiguities
            )
            self.last_ambiguities = new_ambs
            return answer
        if query_type == QT_CREDITS_COMPARE:
            return sh.handle_credits_compare(query, resolver, verbose)

        if query_type == QT_UNIT_CONTENT:
            return sh.handle_unit_content(course_code, unit_number, self.vector_db)

        if query_type == QT_FULL_SYLLABUS_MULTI:
            result = sh.handle_full_syllabus_multi(query, resolver, self.vector_db)
            if result:
                return result
            query_type = QT_FULL_SYLLABUS

        if query_type == QT_FULL_SYLLABUS:
            answer, res_code, new_ambs = sh.handle_full_syllabus(
                course_code, query, resolver, self.vector_db, self.ollama, self.last_ambiguities
            )
            self.last_ambiguities = new_ambs
            if res_code and res_code != course_code:
                self.last_course_code = res_code
                self.last_course_name = resolver.get_name_from_code(res_code)
            return answer

        return "Not found."

    def _resolve_course(
        self,
        query_text: str,
        query_type: Optional[str],
        session_id: Optional[str],
        verbose: bool,
    ) -> Tuple[Optional[str], Optional[str]]:
        resolver = self.course_resolver
        
        # Extract explicit course code (case-normalized)
        explicit = self._extract_course_code(query_text)
        
        if explicit:
            name = resolver.get_name_from_code(explicit)
            if name:
                if verbose:
                    print(f"[EXPLICIT CODE] {explicit} → {name}\n")
                return explicit, name
            
            if self._is_valid_code_format(explicit):
                if verbose:
                    print(f"[INVALID CODE] {explicit} not found in resolver\n")
                return explicit, None

        # For COURSE_NAME queries, extract course name from query BEFORE session fallback
        if query_type == QT_COURSE_NAME:
            course_name_in_query = self._extract_entity_for_metadata_query(query_text, "name")
            if course_name_in_query and course_name_in_query.strip() and course_name_in_query != query_text:
                code, name, _ = resolver.resolve_code(course_name_in_query, allow_fuzzy=False)
                if code:
                    if verbose:
                        print(f"[EXPLICIT NAME] Resolved '{course_name_in_query}' → {name} ({code})\n")
                    return code, name
        
        # For COURSE_CODE queries, extract course name BEFORE session fallback
        if query_type == QT_COURSE_CODE:
            from structured_handlers import _extract_course_name_for_code_query
            name_q = _extract_course_name_for_code_query(query_text)
            if name_q and name_q != query_text:
                code, name, _ = resolver.resolve_code(name_q, allow_fuzzy=False)
                if code:
                    if verbose:
                        print(f"[EXPLICIT NAME] Resolved '{name_q}' → {name} ({code})\n")
                    return code, name
        
        # Generic resolver (non-metadata queries)
        if query_type not in {QT_COURSE_NAME, QT_COURSE_CODE, QT_CREDITS, "STAFF_INFO"}:
            code, name, _ = resolver.resolve_code(query_text, allow_fuzzy=False)
            if code:
                return code, name

        # BUG FIX 4: Session fallback for queries without explicit entities
        # This is critical for "unit 1" to work after "CCS342 subject name"
        if query_type in {QT_UNIT_CONTENT, QT_CREDITS, QT_COURSE_NAME, "STAFF_INFO", 
                          QT_OBJECTIVES, QT_OUTCOMES, QT_TEXTBOOKS, QT_REFERENCES}:
            session_course = self._get_session_course(session_id)
            if session_course:
                sc_name = resolver.get_name_from_code(session_course)
                if verbose:
                    print(f"[SESSION FALLBACK] {query_type} using session course → {sc_name} ({session_course})\n")
                return session_course, sc_name
        
        return None, None

    def _get_session_course(self, session_id: Optional[str]) -> Optional[str]:
        if session_id and self.session_manager:
            return self.session_manager.get_active_course(session_id)
        return self.last_course_code

    def _is_bare_course_code(self, query: str) -> Optional[str]:
        q = query.strip().upper()
        m = re.match(r'^([A-Z]{2,4})(\d{3,5})$', q)
        if m:
            code = f"{m.group(1)}{m.group(2)}"
            if self.course_resolver.get_name_from_code(code):
                return code
        return None

    def _is_numeric_selection(self, query: str) -> Optional[int]:
        q = query.strip()
        if q.isdigit():
            n = int(q)
            if 1 <= n <= len(self.last_ambiguities):
                return n
        return None

    def _is_semester_query(self, query: str) -> bool:
        q = query.lower()
        sem = [r'\bsemester\s+\d+\b', r'\bsem\s+\d+\b', r'\b\d+(?:st|nd|rd|th)\s+semester\b']
        agg = [r'\bnumber\s+of\b', r'\bhow\s+many\b', r'\btotal\b', r'\bhighest\b', r'\blowest\b', r'\baverage\b', r'\bcount\b']
        return (any(re.search(p, q) for p in sem) and any(re.search(p, q) for p in agg))

    def _is_lab_query(self, query: str) -> bool:
        q = query.lower()
        return any(re.search(r'\b' + re.escape(k) + r'\b', q) for k in ['lab', 'laboratory', 'practical', 'exercise', 'experiment', 'workshop'])

    def _extract_course_code(self, query: str) -> Optional[str]:
        normalized_query = query.upper()
        
        for p in [r'\b([A-Z]{2,4})\s*(\d{3,5})\b', r'\b([A-Z]{3})(\d{3})\b']:
            m = re.search(p, normalized_query)
            if m:
                code = f"{m.group(1)}{m.group(2)}".upper()
                if self.course_resolver.get_name_from_code(code):
                    return code
                if self._is_valid_code_format(code):
                    return code
        return None

    def _extract_entity_for_metadata_query(self, query: str, query_type: str) -> str:
        q = query.lower()
        
        # Pattern: "metadata FOR/OF entity"
        for_of_pattern = rf'(?:course\s+|subject\s+)?{query_type}\s+(?:for|of)\s+(.+)$'
        match = re.search(for_of_pattern, q)
        if match:
            entity = match.group(1).strip()
            entity = re.sub(r'\s+(?:course|subject)\s*$', '', entity)
            return entity
        
        # Pattern: "what is the course/subject name for entity"
        what_pattern = rf'what(?:\'s| is)\s+the\s+(?:course\s+|subject\s+)?{query_type}\s+(?:for|of)?\s*(.+)$'
        match = re.search(what_pattern, q)
        if match:
            entity = match.group(1).strip()
            entity = re.sub(r'\s+(?:course|subject)\s*$', '', entity)
            return entity
        
        # Pattern: "entity course/subject name" (suffix)
        suffix_pattern = rf'^(.+?)\s+(?:course\s+|subject\s+)?{query_type}\s*$'
        match = re.search(suffix_pattern, q)
        if match:
            entity = match.group(1).strip()
            if entity not in {'what', 'what is', "what's", 'whats', 'the'}:
                return entity
        
        return query

    def _is_valid_code_format(self, code: str) -> bool:
        return bool(re.match(r'^[A-Z]{2,4}\d{3,5}$', code))

    def _extract_unit_number(self, query: str) -> Tuple[Optional[str], bool]:
        q = query.lower()
        VALID = {'I', 'II', 'III', 'IV', 'V'}
        m = re.search(r'\bunit\s*([IVX]+)\b', q)
        if m:
            r = m.group(1).upper()
            return r, r not in VALID
        m = re.search(r'\bunit\s*(\d+)\b', q)
        if m:
            num = int(m.group(1))
            mapping = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
            if num in mapping: return mapping[num], False
            return str(num), True
        return None, False

    def _check_db_status(self) -> bool:
        if self.vector_db is None: return False
        try:
            info = self.vector_db.client.get_collection(self.vector_db.collection_name)
            return info.points_count > 0
        except Exception: return False

    def _blocked(self, msg: str, method: str = "blocked") -> Dict[str, Any]:
        return {"query": "", "answer": msg, "method": method, "chunks_retrieved": 0, "chunks_used": 0, "llm_used": False, "processing_time": 0.0}

    def _log_resolution(self, dept, code, name, unit, qt, is_struct, is_lab, session_id):
        print(f"[RESOLUTION RESULT]")
        print(f"  Department:  {dept}")
        print(f"  Course code: {code or 'None'}")
        print(f"  Course name: {name or 'None'}")
        print(f"  Unit:        {unit or 'None'}")
        print(f"  Query type:  {qt or 'SEMANTIC'}")
        print(f"  Structured:  {is_struct}")
        if is_struct and qt and qt in ALL_STRUCTURED_TYPES:
            print(f"  Routing:     DETERMINISTIC (no LLM)")
        elif is_struct:
            print(f"  Routing:     STRUCTURED")
        else:
            print(f"  Routing:     SEMANTIC (LLM)")
        print(f"  Lab query:   {is_lab}")
        if session_id and self.session_manager:
            info = self.session_manager.get_session_info(session_id)
            print(f"\n[SESSION STATE]\n  {info}")