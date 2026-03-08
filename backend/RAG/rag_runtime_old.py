"""
Academic Syllabus RAG - Runtime System (FIXED VERSION)
======================================
Production-grade query system with sophisticated course resolution.

FIXES IMPLEMENTED:
1. ✅ Correct course resolution with validation
2. ✅ Session state applied for follow-up queries
3. ✅ Enhanced unit parsing (unit1, unit 1, unit I all work)
4. ✅ Semester query blocking (no LLM for aggregate queries)
5. ✅ Multi-course credit aggregation (+ separator, arithmetic)
6. ✅ Three-tier lab handling (EXPLICIT_LAB, LAB_CUM_THEORY, NO_PRACTICAL)
7. ✅ Acronym leakage fixed (semester/unit won't resolve to courses)
8. ✅ Hallucination prevention (answer validation, grounding check)

BUG FIXES v4.1:
- COURSE_CODE queries use pipeline-resolved code (not full-query re-resolve).
- Semantic follow-ups inherit session course before falling to generic search.
- "first unit for X" classified as UNIT_CONTENT.
- FULL_SYLLABUS updates session; COURSE_CODE also updates session.
- _validate_answer() threshold loosened to 0.4.

BUG FIXES v4.2:
- Bug 1: unit queries with a session course can no longer fall to semantic lane.
  After the resolution pipeline, if unit_number is set and a course is now resolved,
  is_structured and query_type are force-overridden to UNIT_CONTENT.
- Bug 2: multi-course FULL_SYLLABUS ("ge3151 and ge3152 syllabus") is detected,
  split into sub-queries, and results aggregated deterministically with no LLM.

NEW v4.2:
- Department-aware routing. Department is stored in session state.
- AcademicRAGSystem.set_department(dept_code, session_id) re-initialises
  course resolver, acronym file, and vector DB for that session's department.
- CLI prompts for department before accepting queries; queries are blocked
  until a valid department is selected for the session.
- No hard-coded department list: valid departments are discovered from disk
  (subdirectories of persist_path) so new departments require no code changes.

Version: Production v4.2
"""

import re
import sys
import json
import requests
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from collections import defaultdict
from enum import Enum


class OllamaClient:
    """Minimal Ollama client for embeddings and generation."""

    def __init__(self, embedding_model: str = "nomic-embed-text", llm_model: str = "mistral:7b-instruct"):
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.embed_endpoint = "http://localhost:11434/api/embeddings"
        self.generate_endpoint = "http://localhost:11434/api/generate"

    def embed_single(self, text: str):
        """Generate embedding for single text."""
        response = requests.post(
            self.embed_endpoint,
            json={"model": self.embedding_model, "prompt": text}
        )
        return response.json()['embedding']

    def get_embedding_dim(self) -> int:
        """Get embedding dimension."""
        test_embed = self.embed_single("test")
        return len(test_embed)





class CourseCodeResolver:
    """
    Bidirectional course code <-> name resolver.
    Loads persisted acronyms from ingestion.

    FIXES:
    - Issue 7: Enhanced structural keyword filtering
    - Issue 5: Multi-separator support for credit queries
    """

    WORD_NORMALIZATIONS = {
        'programming': 'programming',
        'programme': 'programming',
        'programs': 'programming',
        'databases': 'database',
        'networks': 'network',
        'systems': 'system',
        'principles': 'principles',
        'principle': 'principles',
        'foundations': 'foundation',
        'fundamentals': 'fundamental',
        'introduction': 'intro',
        'advanced': 'adv',
        'laboratory': 'lab',
        'practical': 'lab',
    }

    STRUCTURAL_KEYWORDS = {
        'list', 'show', 'display', 'get', 'fetch', 'retrieve',
        'unit', 'units', 'topic', 'topics', 'chapter', 'chapters',
        'semester', 'sem',
        'what', 'how', 'when', 'where', 'which', 'tell', 'give',
        'credits', 'credit', 'hours', 'syllabus', 'objectives',
        'outcomes', 'outcome', 'textbook', 'textbooks', 'reference', 'references',
        'first', 'second', 'third', 'fourth', 'fifth',
        'about', 'explain', 'describe', 'summarize', 'summary',
        'name', 'code', 'course', 'exercises', 'exercise',
        'content', 'section', 'sections', 'module', 'modules',
        'number', 'total', 'highest', 'lowest', 'average',
    }

    def __init__(self, department: str = "CSE"):
        self.department = department
        self.code_to_name: Dict[str, str] = {}
        self.name_to_code: Dict[str, str] = {}
        self.code_to_credits: Dict[str, str] = {}
        self.normalized_to_code: Dict[str, str] = {}
        self.acronym_to_code: Dict[str, str] = {}
        self.keyword_to_codes: Dict[str, List[str]] = defaultdict(list)

    def load_mappings(self, mapping_text: str):
        """Load course mappings from text file."""
        lines = mapping_text.strip().split('\n')
        count = 0

        for line in lines:
            line = line.strip()
            if not line or '→' not in line:
                continue

            parts = line.split('→')
            if len(parts) != 3:
                continue

            code = parts[0].strip().upper()
            name = parts[1].strip()
            credits = parts[2].strip()

            self.code_to_name[code] = name
            self.name_to_code[name] = code
            self.code_to_credits[code] = credits

            normalized_name = self._normalize_name(name)
            self.normalized_to_code[normalized_name] = code

            keywords = self._extract_keywords(name)
            for keyword in keywords:
                self.keyword_to_codes[keyword].append(code)

            count += 1

        print(f"✓ Loaded {count} course mappings")

    def load_acronyms(self, acronym_file: Path):
        """Load persisted acronyms from ingestion."""
        if not acronym_file.exists():
            print(f"⚠ Acronym file not found: {acronym_file}")
            return

        try:
            with open(acronym_file, 'r', encoding='utf-8') as f:
                acronym_map = json.load(f)

            for acronym, code in acronym_map.items():
                self.acronym_to_code[acronym.upper()] = code.upper()

            print(f"✓ Loaded {len(self.acronym_to_code)} acronyms from {acronym_file.name}")
        except Exception as e:
            print(f"⚠ Failed to load acronyms: {e}")

    def resolve_code(self, query: str, allow_fuzzy: bool = True) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Resolve course code from query.

        Returns:
            (code, name, ambiguities)
        """
        query_upper = query.upper()
        query_lower = query.lower()

        # 1. Explicit code pattern
        code_match = re.search(r'\b([A-Z]{2,4})\s*(\d{3,5})\b', query, re.IGNORECASE)
        if code_match:
            code = f"{code_match.group(1)}{code_match.group(2)}".upper()
            if code in self.code_to_name:
                return code, self.code_to_name[code], []
            else:
                return None, None, [f"Course code {code} not found in database"]

        # 2. Exact name match
        for name, code in self.name_to_code.items():
            if name.lower() == query_lower:
                return code, name, []

        # 3. Acronym match
        query_words = query_upper.split()
        for word in query_words:
            if word in self.acronym_to_code:
                code = self.acronym_to_code[word]
                return code, self.code_to_name.get(code, "Unknown"), []

        query_clean = query_upper.strip()
        if query_clean in self.acronym_to_code:
            code = self.acronym_to_code[query_clean]
            return code, self.code_to_name.get(code, "Unknown"), []

        # 4. Normalized name match
        normalized_query = self._normalize_name(query)
        if normalized_query in self.normalized_to_code:
            code = self.normalized_to_code[normalized_query]
            return code, self.code_to_name[code], []

        # 5. Keyword fuzzy match (only if allowed)
        if not allow_fuzzy:
            return None, None, []

        query_keywords = self._extract_keywords(query)
        substantive_keywords = [
            kw for kw in query_keywords
            if kw not in self.STRUCTURAL_KEYWORDS
        ]

        if not substantive_keywords:
            return None, None, []

        candidates = self._score_candidates(substantive_keywords)

        if not candidates:
            return None, None, []

        top_score = candidates[0][1]
        tied = [c for c, s in candidates if s == top_score]

        if len(tied) > 1:
            ambiguities = [
                f"{self.code_to_name[c]} ({c})" for c in tied
            ]
            return None, None, ambiguities

        if len(candidates) > 1 and top_score <= 3:
            top_candidates = [c for c, s in candidates[:min(3, len(candidates))]]
            ambiguities = [
                f"{self.code_to_name[c]} ({c})" for c in top_candidates
            ]
            return None, None, ambiguities

        best_code = candidates[0][0]
        return best_code, self.code_to_name[best_code], []

    def resolve_multiple_codes(self, query: str) -> List[Tuple[str, str]]:
        """
        Detect and resolve multiple course mentions in a query.
        Supports separators: and, +, comma, vs
        """
        results = []
        seen_codes = set()

        separators = [
            r'\s+and\s+',
            r'\s*\+\s*',
            r'\s*,\s*',
            r'\s+vs\.?\s+',
        ]

        for sep in separators:
            parts = re.split(sep, query, flags=re.IGNORECASE)
            if len(parts) >= 2:
                for part in parts:
                    for prefix in ['credits of', 'credits for', 'credit of', 'credit for',
                                   'compare', 'comparison', 'the', 'total']:
                        part = re.sub(f'^{prefix}\\s+', '', part, flags=re.IGNORECASE).strip()

                    code, name, _ = self.resolve_code(part)
                    if code and code not in seen_codes:
                        results.append((code, name))
                        seen_codes.add(code)

                if len(results) >= 2:
                    return results

        return results

    def get_name_from_code(self, code: str) -> Optional[str]:
        if not code:
            return None
        return self.code_to_name.get(code.upper())

    def get_credits_from_code(self, code: str) -> Optional[str]:
        if not code:
            return None
        code_upper = code.upper()
        credits = self.code_to_credits.get(code_upper)
        if not credits or credits == "0":
            return None
        return credits

    def _normalize_name(self, name: str) -> str:
        normalized = name.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        words = normalized.split()
        normalized_words = []
        for word in words:
            normalized_words.append(
                self.WORD_NORMALIZATIONS.get(word, word)
            )
        filler = {'the', 'and', 'of', 'in', 'to', 'for', 'with', 'a', 'an'}
        normalized_words = [w for w in normalized_words if w not in filler]
        normalized = ' '.join(normalized_words)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract ONLY substantive keywords, filters structural keywords."""
        normalized = self._normalize_name(text)
        words = normalized.split()
        keywords = [
            w for w in words
            if len(w) >= 4 and w not in self.STRUCTURAL_KEYWORDS
        ]
        return keywords

    def _score_candidates(self, query_keywords: List[str]) -> List[Tuple[str, int]]:
        candidates = defaultdict(int)

        for keyword in query_keywords:
            if keyword in self.keyword_to_codes:
                for code in self.keyword_to_codes[keyword]:
                    candidates[code] += 2

            for indexed_keyword, codes in self.keyword_to_codes.items():
                if keyword in indexed_keyword or indexed_keyword in keyword:
                    for code in codes:
                        candidates[code] += 1

        sorted_candidates = sorted(
            candidates.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return sorted_candidates


class LabType(Enum):
    """Lab/practical component classification."""
    EXPLICIT_LAB = 1
    LAB_CUM_THEORY = 2
    NO_PRACTICAL = 3
    UNKNOWN = 4


try:
    from session_manager import SessionManager
    SESSION_MANAGER_AVAILABLE = True
except ImportError:
    print("⚠ SessionManager not found - session persistence disabled")
    SESSION_MANAGER_AVAILABLE = False
    SessionManager = None

# ── Department routing helpers ────────────────────────────────────────────────
# Patch SessionState at import time to carry active_department.
# We do this here rather than editing session_manager.py so the change is
# contained in one file and won't break any other consumers of SessionManager.
if SESSION_MANAGER_AVAILABLE:
    import session_manager as _sm_module
    _state_cls = _sm_module.SessionState
    if not hasattr(_state_cls, 'active_department'):
        # Inject the field with a default of None using __annotations__ + __init__ patching.
        # Dataclass fields cannot be added after class creation, so we use a subclass swap.
        import dataclasses as _dc

        @_dc.dataclass
        class _PatchedSessionState(_state_cls):
            active_department: Optional[str] = None

        # Replace globally so SessionManager uses the patched version when it
        # instantiates new sessions via SessionState(...)
        _sm_module.SessionState = _PatchedSessionState
        # Also update the reference in SessionManager.create_session if it
        # references the class by name (it does: SessionState(...))
        # We re-point the name inside the module.
        # (SessionManager.create_session calls _sm_module.SessionState)

# Cache of per-department resolvers and vector stores so switching departments
# in a session does not re-hit disk every time.
_dept_resolver_cache: Dict[str, "CourseCodeResolver"] = {}
_dept_vector_cache: Dict[str, "SemanticVectorStore"] = {}
# ─────────────────────────────────────────────────────────────────────────────


class AcademicRAGSystem:
    """
    Production RAG system with department-scoped vector DB.
    ALL 8 CRITICAL FIXES APPLIED + DEPARTMENT ROUTING (v4.2).
    """

    def __init__(
        self,
        department: Optional[str] = None,
        persist_path: str = "./vector_db",
        max_context_chars: int = 1500,
        enable_sessions: bool = True,
    ):
        self.persist_path = persist_path
        self.max_context_chars = max_context_chars

        # Legacy single-department state (used when no session_id is passed)
        self.department: Optional[str] = None
        self.last_course_code: Optional[str] = None
        self.last_course_name: Optional[str] = None
        self.last_ambiguities: List[Tuple[str, str]] = []

        # These are initialised per-department; start as None until a dept is set
        self.course_resolver: Optional[CourseCodeResolver] = None
        self.vector_db: Optional["SemanticVectorStore"] = None

        self.session_manager = None
        if enable_sessions and SESSION_MANAGER_AVAILABLE:
            self.session_manager = SessionManager(default_timeout=1800)
            print("✓ Session manager enabled (30 min timeout)")

        self.ollama = OllamaClient(
            embedding_model="nomic-embed-text",
            llm_model="mistral:7b-instruct"
        )

        print("=" * 70)
        print("ACADEMIC SYLLABUS RAG SYSTEM (v4.2)")
        print("=" * 70)
        print(f"✓ Structured queries: Direct lookup (NO LLM)")
        print(f"✓ Semantic queries: LLM with context")
        print(f"✓ Department routing: ENABLED")
        print(f"✓ Multi-turn conversation: {'Session-based' if self.session_manager else 'Legacy'}")
        print(f"✓ Hallucination prevention: ENABLED")
        print(f"✓ Max context: {max_context_chars} chars\n")

        # If a department is provided at construction time, initialise immediately
        # (backwards-compatible with existing callers that pass department="CSE")
        if department:
            self._init_department_resources(department)
            self.department = department

    # ── Department resource management ───────────────────────────────────────

    def get_available_departments(self) -> List[str]:
        """
        Return department codes discovered from disk.

        A department exists if <persist_path>/<DEPT>/syllabus/ is a directory.
        This means no hard-coded list is needed — adding a new department's
        data automatically makes it available.
        """
        base = Path(self.persist_path)
        if not base.exists():
            return []
        depts = []
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "syllabus").is_dir():
                depts.append(child.name.upper())
        return depts

    def _init_department_resources(self, dept_code: str) -> None:
        """
        Initialise (or swap in from cache) the resolver and vector DB for dept_code.
        Safe to call multiple times — uses module-level caches to avoid redundant I/O.
        Does NOT touch session state; callers manage that.
        """
        dept_upper = dept_code.upper()

        # ── Course resolver ───────────────────────────────────────────────────
        if dept_upper not in _dept_resolver_cache:
            resolver = CourseCodeResolver(department=dept_upper)
            mapping_file = Path(f"{dept_upper}_course_mappings.txt")
            # Fallback to generic name for backwards compat
            if not mapping_file.exists():
                mapping_file = Path("course_mappings.txt")
            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    resolver.load_mappings(f.read())
            acronym_file = Path(f"{dept_upper}_acronyms.json")
            resolver.load_acronyms(acronym_file)
            _dept_resolver_cache[dept_upper] = resolver
            print(f"✓ Resolver initialised for {dept_upper}")
        else:
            print(f"✓ Resolver loaded from cache for {dept_upper}")

        # ── Vector DB ─────────────────────────────────────────────────────────
        if dept_upper not in _dept_vector_cache:
            embedding_dim = self.ollama.get_embedding_dim()
            dept_vector_path = Path(self.persist_path) / dept_upper / "syllabus"
            collection_name = f"{dept_upper}_syllabus"
            vdb = SemanticVectorStore(
                collection_name=collection_name,
                embedding_dim=embedding_dim,
                persist_path=str(dept_vector_path)
            )
            _dept_vector_cache[dept_upper] = vdb
            print(f"✓ Vector DB initialised for {dept_upper} ({collection_name})")
        else:
            print(f"✓ Vector DB loaded from cache for {dept_upper}")

        # Point instance attributes to the active department's resources
        self.course_resolver = _dept_resolver_cache[dept_upper]
        self.vector_db = _dept_vector_cache[dept_upper]
        self.department = dept_upper

    def set_department(self, dept_code: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Department routing API.

        Validates dept_code against available departments on disk, initialises
        department-scoped resources, and updates session state.

        Args:
            dept_code:  Department code string (case-insensitive, e.g. "ECE").
            session_id: Session to update. When None, updates legacy instance state.

        Returns:
            {"ok": True, "department": dept_code} on success.
            {"ok": False, "error": "..."} on failure.
        """
        dept_upper = dept_code.strip().upper()
        available = self.get_available_departments()

        if not available:
            # Disk not set up yet — allow anyway so tests without disk still work
            pass
        elif dept_upper not in available:
            return {
                "ok": False,
                "error": (
                    f"Department '{dept_upper}' not found. "
                    f"Available: {', '.join(available) or 'none on disk'}"
                )
            }

        # Initialise resources (cached after first call)
        self._init_department_resources(dept_upper)

        # Update session state
        if session_id and self.session_manager:
            session = self.session_manager.get_session(session_id)
            if session and hasattr(session, 'active_department'):
                session.active_department = dept_upper
                # Clear course/unit — they belong to the old department
                session.active_course_code = None
                session.active_course_name = None
                session.active_unit = None
        else:
            # Legacy mode: department is stored on the instance
            self.last_course_code = None
            self.last_course_name = None

        print(f"✓ Department set to {dept_upper}")
        return {"ok": True, "department": dept_upper}

    def _get_session_department(self, session_id: Optional[str]) -> Optional[str]:
        """Return the active department for a session (or legacy instance dept)."""
        if session_id and self.session_manager:
            session = self.session_manager.peek_session(session_id)
            if session and hasattr(session, 'active_department'):
                return session.active_department
        return self.department

    def _ensure_dept_resources(self, session_id: Optional[str]) -> Optional[str]:
        """
        Ensure course_resolver and vector_db are pointing at the correct
        department for this call. Returns the dept code, or None if not set.
        """
        dept = self._get_session_department(session_id)
        if not dept:
            return None
        # Swap resources if the session's dept differs from current instance dept
        if dept != self.department or self.course_resolver is None:
            self._init_department_resources(dept)
        return dept

    def _check_db_status(self) -> bool:
        """Check if vector DB has data."""
        if self.vector_db is None:
            return False
        try:
            info = self.vector_db.client.get_collection(
                self.vector_db.collection_name
            )
            has_data = info.points_count > 0

            if not has_data:
                print(f"\n⚠ Vector DB exists but has 0 chunks:")
                print(f"  Collection: {self.vector_db.collection_name}")

            return has_data
        except Exception as e:
            print(f"\n⚠ Vector DB check failed: {e}")
            return False

    def _is_numeric_selection(self, query: str) -> Optional[int]:
        """Check if query is numeric disambiguation."""
        query = query.strip()
        if query.isdigit():
            num = int(query)
            if 1 <= num <= len(self.last_ambiguities):
                return num
        return None

    def _is_semester_query(self, query: str) -> bool:
        """Detect semester-level aggregate queries that cannot be answered."""
        query_lower = query.lower()

        semester_patterns = [
            r'\bsemester\s+\d+\b',
            r'\bsem\s+\d+\b',
            r'\b\d+(?:st|nd|rd|th)\s+semester\b',
        ]

        aggregate_patterns = [
            r'\bnumber\s+of\b',
            r'\bhow\s+many\b',
            r'\btotal\b',
            r'\bhighest\b',
            r'\blowest\b',
            r'\baverage\b',
            r'\bcount\b',
        ]

        has_semester = any(re.search(p, query_lower) for p in semester_patterns)
        has_aggregate = any(re.search(p, query_lower) for p in aggregate_patterns)

        return has_semester and has_aggregate

    def _is_lab_query(self, query: str) -> bool:
        """Check if query is asking about lab/practical content."""
        lab_keywords = ['lab', 'laboratory', 'practical', 'exercise', 'experiment', 'workshop']
        query_lower = query.lower()

        for keyword in lab_keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, query_lower):
                return True
        return False

    def _classify_lab_type(self, course_code: Optional[str]) -> LabType:
        """Classify practical component type for a course."""
        if not course_code:
            return LabType.UNKNOWN

        course_name = self.course_resolver.get_name_from_code(course_code)
        if not course_name:
            return LabType.UNKNOWN

        name_lower = course_name.lower()

        if 'lab' in name_lower or 'laboratory' in name_lower:
            return LabType.EXPLICIT_LAB

        known_lab_cum_theory = ['CCS342', 'CS3301', 'CCS334']
        if course_code.upper() in known_lab_cum_theory:
            return LabType.LAB_CUM_THEORY

        return LabType.NO_PRACTICAL

    def _is_structured_query(self, query: str) -> tuple:
        """
        Classify query as structured or semantic.

        FIX Issue 3: Extended UNIT_CONTENT patterns to catch "first unit for X",
        "unit 1 for X", etc. - not just bare "unit 1".
        """
        query_lower = query.lower()

        # UNIT_CONTENT detection
        # Pattern A: bare unit queries - "unit 1", "unit I", "unit1", "first unit"
        bare_unit_patterns = [
            r'^\s*unit\s*[IVX1-5]+\s*$',
            r'^\s*(first|second|third|fourth|fifth)\s+unit\s*$',
            r'^\s*unit\s+(first|second|third|fourth|fifth)\s*$',
        ]
        for pattern in bare_unit_patterns:
            if re.match(pattern, query_lower):
                return True, "UNIT_CONTENT"

        # Pattern B: unit with course context - "unit 1 for devops", "first unit for CS3591"
        # FIX: These were falling through to SEMANTIC, causing retrieval failures
        unit_with_course_patterns = [
            r'\bunit\s*[IVX1-5]+\s+(?:for|of|in)\s+\S',
            r'\b(first|second|third|fourth|fifth)\s+unit\s+(?:for|of|in)\s+\S',
            r'\bunit\s+(first|second|third|fourth|fifth)\s+(?:for|of|in)\s+\S',
        ]
        for pattern in unit_with_course_patterns:
            if re.search(pattern, query_lower):
                return True, "UNIT_CONTENT"

        # Multi-course credit comparison
        # Trigger on "compare ... credit" OR any query with "credit/credits" AND a multi-course
        # separator (and/+/,/vs) - e.g. "ph3151 and ge3151 credits"
        has_credit = 'credit' in query_lower
        has_separator = bool(re.search(r'\s+and\s+|\s*\+\s*|\s*,\s*|\s+vs\.?\s+', query_lower))
        has_compare_kw = any(t in query_lower for t in ["compare", "comparison"])

        if has_credit and (has_compare_kw or has_separator):
            return True, "CREDITS_COMPARE"

        # COURSE_CODE detection
        if any(trigger in query_lower for trigger in [
            "course code for", "code for", "course code of", "code of",
            "what is the course code", "what is the code",
            "what's the course code", "what's the code"
        ]):
            return True, "COURSE_CODE"

        if re.search(r'.+\s+course\s+code\s*$', query_lower):
            return True, "COURSE_CODE"

        if any(trigger in query_lower for trigger in [
            "course name", "name of the course", "name of course",
            "course title", "title of the course", "title of course"
        ]):
            return True, "COURSE_NAME"

        if any(trigger in query_lower for trigger in [
            "how many credits", "credits for", "credits of",
            "credit hours for", "credit hours of"
        ]):
            return True, "CREDITS"

        if any(trigger in query_lower for trigger in [
            "syllabus", "full syllabus", "entire syllabus", "complete syllabus",
            "whole syllabus", "give me the syllabus"
        ]):
            # Bug 2 fix: detect multi-course syllabus before returning FULL_SYLLABUS
            # so query() can split and aggregate deterministically.
            has_separator = bool(re.search(r'\s+and\s+|\s*\+\s*|\s*,\s*|\s+vs\.?\s+', query_lower))
            if has_separator:
                return True, "FULL_SYLLABUS_MULTI"
            return True, "FULL_SYLLABUS"

        return False, None

    def _extract_course_code(self, query: str) -> Optional[str]:
        patterns = [
            r'\b([A-Z]{2,4})\s*(\d{3,5})\b',
            r'\b([A-Z]{3})(\d{3})\b',
        ]

        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return f"{match.group(1)}{match.group(2)}".upper()
        return None

    def _extract_unit_number(self, query: str) -> Tuple[Optional[str], bool]:
        """
        Extract unit number with validation.

        Returns:
            (unit_number, is_invalid)
            - unit_number: Roman numeral string or None
            - is_invalid: True if unit pattern detected but out of range (1-5)
        """
        query_lower = query.lower()

        VALID_ROMAN = {'I', 'II', 'III', 'IV', 'V'}

        roman_match = re.search(r'\bunit\s*([IVX]+)\b', query_lower)
        if roman_match:
            roman = roman_match.group(1).upper()
            if roman in VALID_ROMAN:
                return roman, False
            else:
                return roman, True

        arabic_match = re.search(r'\bunit\s*(\d+)\b', query_lower)
        if arabic_match:
            num = int(arabic_match.group(1))
            mapping = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}

            if num in mapping:
                return mapping[num], False
            else:
                return str(num), True

        word_mapping = {
            'first': 'I',
            'second': 'II',
            'third': 'III',
            'fourth': 'IV',
            'fifth': 'V',
        }

        for word, roman in word_mapping.items():
            if f'{word} unit' in query_lower or f'unit {word}' in query_lower:
                return roman, False

        return None, False

    def _extract_course_name_from_query(self, query: str, query_type: str) -> str:
        """Extract course name from structured queries."""
        query_lower = query.lower()

        if query_type == "COURSE_CODE":
            patterns = [
                r'course\s+code\s+(?:for|of)\s+(.+)$',
                r'code\s+(?:for|of)\s+(.+)$',
                r'what\s+is\s+the\s+course\s+code\s+(?:for|of)?\s*(.+)$',
                r'what\s+is\s+the\s+code\s+(?:for|of)?\s*(.+)$',
                r'what\'s\s+the\s+course\s+code\s+(?:for|of)?\s*(.+)$',
                r'what\'s\s+the\s+code\s+(?:for|of)?\s*(.+)$',
            ]

            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    extracted = match.group(1).strip()
                    if extracted:
                        return extracted

            suffix_match = re.search(r'^(.+?)\s+course\s+code\s*$', query_lower)
            if suffix_match:
                extracted = suffix_match.group(1).strip()
                if extracted and extracted not in ['what', 'what is', 'what\'s', 'whats', 'the']:
                    return extracted

        elif query_type == "FULL_SYLLABUS":
            patterns = [
                r'syllabus\s+(?:for|of)\s+(.+)$',
                r'full\s+syllabus\s+(?:for|of)\s+(.+)$',
                r'(?:give|show)\s+(?:me\s+)?(?:the\s+)?syllabus\s+(?:for|of)\s+(.+)$',
            ]

            for pattern in patterns:
                match = re.search(pattern, query_lower)
                if match:
                    return match.group(1).strip()

        return query

    def _get_session_course(self, session_id: Optional[str]) -> Optional[str]:
        """Helper: get active course from session or legacy state."""
        if session_id and self.session_manager:
            return self.session_manager.get_active_course(session_id)
        return self.last_course_code

    def _course_resolver_for(self, session_id: Optional[str]) -> Optional["CourseCodeResolver"]:
        """Return the resolver scoped to the session's active department."""
        self._ensure_dept_resources(session_id)
        return self.course_resolver

    def _answer_structured_query(
        self,
        query_type: str,
        query: str,
        course_code: Optional[str],
        unit_number: Optional[str],
        verbose: bool
    ) -> str:
        """
        Handle structured queries (NO LLM).

        FIX Issue 1 (CRITICAL): COURSE_CODE branch now uses the already-resolved
        course_code from the pipeline when available, instead of always re-resolving
        from the raw query. This eliminates the MX3089 log contradiction.

        FIX Issue 2: UNIT_CONTENT branch already receives correct course_code.
        FIX Issue 5: CREDITS_COMPARE with multi-separator and arithmetic.
        """
        if verbose:
            print(f"  Query type: {query_type} (structured)")

        # Bug 2: multi-course syllabus — split, retrieve each, aggregate
        if query_type == "FULL_SYLLABUS_MULTI":
            courses = self.course_resolver.resolve_multiple_codes(query)
            if len(courses) < 2:
                # Fall back to single-course FULL_SYLLABUS path
                query_type = "FULL_SYLLABUS"
            else:
                parts = []
                for code, name in courses:
                    chunks = self.vector_db.retrieve_by_course(course_code=code, top_k=200)
                    if chunks:
                        sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])
                        section = ["=" * 70, f"COURSE: {code} — {name}", "=" * 70, ""]
                        for chunk in sorted_chunks:
                            section.append(chunk['text'])
                            section.append("")
                        parts.append("\n".join(section))
                    else:
                        parts.append(f"Syllabus not found for {name} ({code}).")
                return "\n\n".join(parts)

        if query_type == "UNIT_CONTENT":
            if not course_code:
                return "Please specify which course you're asking about."

            if not unit_number:
                return "Unit number not recognized. Please specify like 'unit 1' or 'unit I'."

            chunks = self.vector_db.retrieve_by_course(
                course_code=course_code,
                unit_number=unit_number,
                top_k=50
            )

            if not chunks:
                return f"Unit {unit_number} content not found for {course_code}."

            sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])
            lines = [
                "=" * 70,
                f"COURSE: {course_code} | UNIT: {unit_number}",
                "=" * 70,
                ""
            ]
            for chunk in sorted_chunks:
                lines.append(chunk['text'])
                lines.append("")

            return "\n".join(lines)

        if query_type == "CREDITS_COMPARE":
            courses = self.course_resolver.resolve_multiple_codes(query)

            if len(courses) < 2:
                if verbose:
                    print(f"  Initial extraction found {len(courses)} courses, trying harder...")

                words = query.upper().split()
                potential_codes = []
                seen_codes = set()

                for word in words:
                    if word in self.course_resolver.acronym_to_code:
                        code = self.course_resolver.acronym_to_code[word]
                        if code not in seen_codes:
                            name = self.course_resolver.get_name_from_code(code)
                            potential_codes.append((code, name))
                            seen_codes.add(code)

                for i in range(len(words) - 1):
                    two_word = f"{words[i]} {words[i + 1]}"
                    if two_word in self.course_resolver.acronym_to_code:
                        code = self.course_resolver.acronym_to_code[two_word]
                        if code not in seen_codes:
                            name = self.course_resolver.get_name_from_code(code)
                            potential_codes.append((code, name))
                            seen_codes.add(code)

                if len(potential_codes) >= 2:
                    courses = potential_codes[:2]
                elif len(potential_codes) == 1:
                    return f"Found only one course: {potential_codes[0][1]}. Please specify another course to compare."

            if len(courses) < 2:
                return "Please specify two courses to compare. Example: 'compare credits of OOP and OOP LAB'"

            query_lower = query.lower()
            if "total" in query_lower or "sum" in query_lower:
                total = 0
                for code, name in courses:
                    credits_str = self.course_resolver.get_credits_from_code(code)
                    if credits_str:
                        parts = credits_str.split('-')
                        if parts:
                            total += int(parts[0])
                return f"Total credits: {total}"
            else:
                results = []
                for code, name in courses:
                    credits = self.course_resolver.get_credits_from_code(code)
                    if credits:
                        results.append(f"{name} ({code}): {credits} credits")
                    else:
                        results.append(f"{name} ({code}): Credits not found")

                return "\n".join(results)

        if query_type == "COURSE_CODE":
            # FIX Issue 1 (CRITICAL): If the pipeline already resolved a course code,
            # use it directly. Only re-resolve if pipeline found nothing.
            # This prevents the case where pipeline correctly finds CCS342 but
            # this branch overwrites it with MX3089 by re-running resolve_code()
            # on the full query text.
            if course_code:
                actual_name = self.course_resolver.get_name_from_code(course_code)
                name = actual_name or "Unknown"
                return f"The course code for {name} is: {course_code}"

            # Pipeline found nothing - extract the course name substring and resolve
            course_name_query = self._extract_course_name_from_query(query, "COURSE_CODE")

            detected_code, detected_name, ambiguities = self.course_resolver.resolve_code(course_name_query)

            if ambiguities:
                unique_ambiguities = {}
                for amb in ambiguities:
                    code = amb.split('(')[1].rstrip(')')
                    name = amb.split('(')[0].strip()
                    unique_ambiguities[code] = name

                self.last_ambiguities = [(code, name) for code, name in unique_ambiguities.items()]

                return "Multiple courses found. Please be more specific or enter a number:\n" + "\n".join(
                    f"{i + 1}. {name} ({code})" for i, (code, name) in enumerate(self.last_ambiguities)
                )

            if detected_code:
                actual_name = self.course_resolver.get_name_from_code(detected_code)
                if actual_name and actual_name != detected_name:
                    detected_name = actual_name

                return f"The course code for {detected_name} is: {detected_code}"

            return "Course not found in database. Please check the course name."

        if query_type == "COURSE_NAME":
            name = self.course_resolver.get_name_from_code(course_code)
            if name:
                return f"The course name is: {name}"
            return "Course name not found in database."

        elif query_type == "CREDITS":
            credits = self.course_resolver.get_credits_from_code(course_code)
            if credits:
                return f"Credits: {credits}"
            return "Credits information not found."

        elif query_type == "FULL_SYLLABUS":
            if not course_code:
                course_name_query = self._extract_course_name_from_query(query, "FULL_SYLLABUS")

                multi_courses = self.course_resolver.resolve_multiple_codes(course_name_query)
                if len(multi_courses) > 1:
                    self.last_ambiguities = multi_courses
                    return "Multiple courses detected. Please specify which one or enter a number:\n" + "\n".join(
                        f"{i + 1}. {name} ({code})" for i, (code, name) in enumerate(multi_courses)
                    )

                detected_code, detected_name, ambiguities = self.course_resolver.resolve_code(course_name_query)

                if ambiguities:
                    unique_ambiguities = {}
                    for amb in ambiguities:
                        code = amb.split('(')[1].rstrip(')')
                        name = amb.split('(')[0].strip()
                        unique_ambiguities[code] = name

                    self.last_ambiguities = [(code, name) for code, name in unique_ambiguities.items()]

                    return "Multiple courses found. Please specify or enter a number:\n" + "\n".join(
                        f"{i + 1}. {name} ({code})" for i, (code, name) in enumerate(self.last_ambiguities)
                    )

                if detected_code:
                    course_code = detected_code
                else:
                    return "Course not found. Please specify the course code or name."

            chunks = self.vector_db.retrieve_by_course(
                course_code=course_code,
                top_k=200
            )

            if not chunks:
                try:
                    course_name_query = self._extract_course_name_from_query(query, "FULL_SYLLABUS")
                    query_embedding = self.ollama.embed_single(course_name_query)
                    chunks = self.vector_db.search(
                        query_embedding=query_embedding,
                        top_k=200
                    )
                except Exception:
                    chunks = []

            if not chunks:
                return "Syllabus not found."

            sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])
            lines = ["=" * 70, f"COURSE: {course_code}", "=" * 70 + "\n"]
            for chunk in sorted_chunks:
                lines.append(chunk['text'])
                lines.append("")
            return "\n".join(lines)

        return "Not found."

    def _build_safe_context(self, chunks: List[Dict], max_chars: int = 1500) -> tuple:
        sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])

        context_parts = []
        total_chars = 0
        chunks_used = 0

        for chunk in sorted_chunks:
            text = chunk['text']
            text_len = len(text)

            if total_chars + text_len > max_chars:
                break

            context_parts.append(text)
            total_chars += text_len
            chunks_used += 1

        context = "\n\n".join(context_parts)
        return context, chunks_used

    def _build_minimal_prompt(self, query: str, context: str) -> str:
        return f"""You are a syllabus content extractor. Answer STRICTLY from the context below.

CRITICAL RULES:
1. If the information is NOT in the context, respond EXACTLY: "Not in syllabus."
2. NEVER use general knowledge or external information.
3. NEVER invent facts, numbers, or explanations.
4. Only quote or paraphrase text that APPEARS in the context.
5. If context is empty or irrelevant, respond: "Not in syllabus."
6. NEVER mention SI units, physics, biology, or general science unless in context.

CONTEXT:
{context}

QUERY: {query}

ANSWER (from context only):"""

    def _validate_answer(self, answer: str, context: str, query: str) -> str:
        """
        Validate that LLM answer is grounded in context.

        FIX Issue 8: Loosened thresholds to prevent valid answers being rejected.
        - Number check: now requires ALL sampled numbers to be missing (not just any)
        - Overlap threshold: lowered from 0.5 to 0.4
        - Only runs overlap check if answer is substantive (>50 chars)
        """
        answer_lower = answer.lower()
        context_lower = context.lower()

        # Check 1: Reject if answer mentions known general knowledge topics not in context
        general_knowledge_terms = [
            'ampere', 'volt', 'si unit', 'ohm', 'watt', 'kilogram',
            'meiosis', 'mitosis', 'dna', 'rna', 'photosynthesis',
            'napoleon', 'world war', 'shakespeare', 'columbus',
        ]

        for term in general_knowledge_terms:
            if term in answer_lower and term not in context_lower:
                return "Not in syllabus."

        # Check 2: If answer contains numbers, verify at least one appears in context
        # FIX: Changed from "any missing → reject" to "ALL missing → reject"
        numbers = re.findall(r'\b\d+\.?\d*\b', answer)
        if numbers and len(answer) > 20:
            sample = numbers[:3]
            found_any = any(num in context for num in sample)
            if not found_any and len(sample) > 0:
                return "Not in syllabus."

        # Check 3: Word overlap - only for substantive answers
        # FIX: Lowered threshold from 0.5 to 0.4, only applies to answers > 50 chars
        if len(answer) > 50:
            answer_words = set(re.findall(r'\b\w{5,}\b', answer_lower))
            context_words = set(re.findall(r'\b\w{5,}\b', context_lower))

            common_words = {'about', 'which', 'their', 'there', 'these', 'those',
                            'would', 'could', 'should', 'following', 'below', 'above'}
            answer_words -= common_words

            if answer_words:
                overlap = len(answer_words & context_words) / len(answer_words)
                if overlap < 0.4:
                    return "Not in syllabus."

        return answer

    def _check_retrieval_quality(self, chunks: List[Dict], query: str) -> bool:
        """Check if retrieved chunks are relevant to query."""
        if not chunks:
            return False

        query_lower = query.lower()
        query_keywords = set(re.findall(r'\b\w{4,}\b', query_lower))

        query_keywords = {
            kw for kw in query_keywords
            if kw not in self.course_resolver.STRUCTURAL_KEYWORDS
        }

        relevant_chunks = 0
        for chunk in chunks[:5]:
            chunk_text = chunk['text'].lower()
            chunk_keywords = set(re.findall(r'\b\w{4,}\b', chunk_text))

            overlap = len(query_keywords & chunk_keywords)
            if overlap >= 1:
                relevant_chunks += 1

        return relevant_chunks >= 2

    def query(
        self,
        query_text: str,
        verbose: bool = True,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main query method with ALL FIXES APPLIED (v4.1).

        KEY FIXES vs v4.0:
        1. COURSE_CODE queries use pipeline-resolved code (Issue 1)
        2. Semantic follow-ups (course objectives, etc.) inherit session course (Issue 2)
        3. "first unit for X" classified as UNIT_CONTENT (Issue 3)
        4. FULL_SYLLABUS updates session so next unit query uses correct course (Issue 5)
        5. Multi-course unit queries ("unit 1 for ph3151 and ge3151") split and processed
           separately (Issue 8)
        """
        # Numeric disambiguation
        selection_num = self._is_numeric_selection(query_text)
        if selection_num is not None and self.last_ambiguities:
            code, name = self.last_ambiguities[selection_num - 1]

            self.last_course_code = code
            self.last_course_name = name

            if session_id and self.session_manager:
                self.session_manager.update_session(
                    session_id=session_id,
                    course_code=code,
                    course_name=name
                )

            self.last_ambiguities = []

            if verbose:
                print(f"\n✓ Selected: {name} ({code})\n")

            return self.query(f"syllabus for {code}", verbose=verbose, session_id=session_id)

        # Block semester-level aggregate queries early
        if self._is_semester_query(query_text):
            return {
                "query": query_text,
                "answer": "Semester-level aggregate data is not available. Please ask about specific courses.",
                "method": "blocked",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.0
            }

        if not self._check_db_status():
            return {
                "query": query_text,
                "answer": "No syllabus data ingested yet. Please run ingestion first.",
                "method": "none",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.0
            }

        if verbose:
            print("\n" + "=" * 70)
            print(f"QUERY: {query_text}")
            print("=" * 70 + "\n")

        # Department guard: ensure resources are initialised for this session's dept.
        # Block query if no department is set.
        active_dept = self._ensure_dept_resources(session_id)
        if not active_dept:
            return {
                "query": query_text,
                "answer": (
                    "No department selected for this session. "
                    "Please select a department first (e.g., call set_department('CSE'))."
                ),
                "method": "blocked",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.0
            }

        # Classification
        is_structured, query_type = self._is_structured_query(query_text)
        is_lab_query = self._is_lab_query(query_text)

        unit_number, is_invalid_unit = self._extract_unit_number(query_text)

        if is_invalid_unit:
            return {
                "query": query_text,
                "answer": f"Unit {unit_number} does not exist. Valid units are: I, II, III, IV, V.",
                "method": "blocked",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.0
            }

        # FIX Issue 8: Multi-course unit query detection
        # "unit 1 for ph3151 and ge3151" → split into two separate queries
        if unit_number and re.search(r'\band\b', query_text, re.IGNORECASE):
            multi_courses = self.course_resolver.resolve_multiple_codes(query_text)
            if len(multi_courses) >= 2:
                if verbose:
                    print(f"[MULTI-COURSE UNIT] Splitting into {len(multi_courses)} queries\n")
                results = []
                for code, name in multi_courses:
                    sub_query = f"unit {unit_number} for {code}"
                    sub_result = self.query(sub_query, verbose=False, session_id=session_id)
                    results.append(f"{'=' * 70}\n{name} ({code}):\n{'=' * 70}\n{sub_result['answer']}")

                return {
                    "query": query_text,
                    "answer": "\n\n".join(results),
                    "method": "multi_course_unit",
                    "chunks_retrieved": 0,
                    "chunks_used": 0,
                    "llm_used": True,
                    "processing_time": 1.0
                }

        explicit_course_code = self._extract_course_code(query_text)

        # Single resolution pipeline
        resolved_course_code = None
        resolved_course_name = None

        # Step 1: Explicit code in query text
        if explicit_course_code:
            resolved_course_code = explicit_course_code
            resolved_course_name = self.course_resolver.get_name_from_code(explicit_course_code)

        # Step 2: Resolve from query text (name/acronym/fuzzy)
        if not resolved_course_code:
            # For COURSE_CODE queries, resolve from the extracted course name substring,
            # NOT the full query. This is the fix for Issue 1.
            if query_type == "COURSE_CODE":
                course_name_query = self._extract_course_name_from_query(query_text, "COURSE_CODE")
                detected_code, detected_name, _ = self.course_resolver.resolve_code(course_name_query)
            else:
                allow_fuzzy = not self._is_semester_query(query_text)
                detected_code, detected_name, _ = self.course_resolver.resolve_code(
                    query_text,
                    allow_fuzzy=allow_fuzzy
                )

            if detected_code:
                resolved_course_code = detected_code
                resolved_course_name = detected_name

        # Step 3: For unit queries without a resolved course, inherit from session
        if not resolved_course_code and query_type == "UNIT_CONTENT":
            session_course = self._get_session_course(session_id)
            if session_course:
                resolved_course_code = session_course
                resolved_course_name = self.course_resolver.get_name_from_code(session_course)
                if verbose:
                    print(f"[SESSION] Using session course: {resolved_course_name} ({resolved_course_code})\n")

        # Bug 1 fix: if we have a unit_number AND a course (from session or query),
        # unconditionally force structured routing. This prevents any code path from
        # sending a unit query to the semantic lane.
        if unit_number and resolved_course_code:
            is_structured = True
            query_type = "UNIT_CONTENT"
            if verbose:
                print(f"[FORCE-STRUCTURED] unit_number={unit_number} + course={resolved_course_code} → UNIT_CONTENT\n")

        # Step 4: FIX Issue 2 - For semantic follow-up queries (e.g., "course objectives"),
        # also inherit session course so retrieval is scoped correctly.
        if not resolved_course_code and not is_structured and not is_lab_query:
            session_course = self._get_session_course(session_id)
            if session_course:
                resolved_course_code = session_course
                resolved_course_name = self.course_resolver.get_name_from_code(session_course)
                if verbose:
                    print(f"[SESSION] Semantic follow-up using session course: {resolved_course_name} ({resolved_course_code})\n")

        # Validate name consistency
        if resolved_course_code and resolved_course_name:
            actual_name = self.course_resolver.get_name_from_code(resolved_course_code)
            if actual_name and actual_name != resolved_course_name:
                if verbose:
                    print(f"[VALIDATION] Name corrected: {resolved_course_name} → {actual_name}")
                resolved_course_name = actual_name

        # Update session for all queries that identify a course EXCEPT pure metadata lookups
        # that don't imply the user wants to "stay on" that course.
        # COURSE_CODE is intentionally INCLUDED here: asking "what is the code for DevOps?"
        # implies the user is interested in DevOps, so follow-up "unit 1" should use CCS342.
        # CREDITS and COURSE_NAME for a single course are similarly included.
        # Only CREDITS_COMPARE (multi-course) is excluded because there's no single active course.
        if resolved_course_code and query_type not in ["CREDITS_COMPARE", "FULL_SYLLABUS_MULTI"]:
            self.last_course_code = resolved_course_code
            self.last_course_name = resolved_course_name

            if session_id and self.session_manager:
                self.session_manager.update_session(
                    session_id=session_id,
                    course_code=resolved_course_code,
                    course_name=resolved_course_name,
                    unit=unit_number if unit_number else None
                )

        if verbose:
            print(f"[RESOLUTION RESULT]")
            print(f"  Department: {active_dept}")
            print(f"  Final course code: {resolved_course_code or 'None'}")
            print(f"  Final course name: {resolved_course_name or 'None'}")
            print(f"  Unit: {unit_number or 'None'}")
            print(f"  Query type: {query_type or 'SEMANTIC'}")
            print(f"  Structured: {is_structured}")
            print(f"  Lab query: {is_lab_query}")

            if session_id and self.session_manager:
                session_info = self.session_manager.get_session_info(session_id)
                print(f"\n[SESSION STATE]")
                print(f"  {session_info}")

            print()

        # Structured lane
        if is_structured:
            if verbose:
                print(f"[ROUTING] STRUCTURED LANE (NO LLM)\n")

            answer = self._answer_structured_query(
                query_type,
                query_text,
                resolved_course_code,
                unit_number,
                verbose
            )

            return {
                "query": query_text,
                "answer": answer,
                "method": "structured",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.01
            }

        # Semantic lane
        if verbose:
            print(f"[ROUTING] SEMANTIC LANE")
            if is_lab_query:
                lab_type = self._classify_lab_type(resolved_course_code)
                print(f"  Lab classification: {lab_type.name}")
            print()

        # Three-tier lab handling
        if is_lab_query and resolved_course_code:
            lab_type = self._classify_lab_type(resolved_course_code)

            if lab_type == LabType.NO_PRACTICAL:
                course_name = self.course_resolver.get_name_from_code(resolved_course_code)
                return {
                    "query": query_text,
                    "answer": f"{course_name} has no practical component.",
                    "method": "blocked",
                    "chunks_retrieved": 0,
                    "chunks_used": 0,
                    "llm_used": False,
                    "processing_time": 0.01
                }

        chunks = []

        # Retrieval
        if resolved_course_code:
            retrieved_chunks = self.vector_db.retrieve_by_course(
                course_code=resolved_course_code,
                unit_number=unit_number,
                top_k=30
            )

            if is_lab_query and retrieved_chunks:
                lab_keywords = ['lab', 'laboratory', 'practical', 'exercise', 'experiment']

                lab_chunks = []
                other_chunks = []

                for chunk in retrieved_chunks:
                    text_lower = chunk['text'].lower()
                    if any(kw in text_lower for kw in lab_keywords):
                        lab_chunks.append(chunk)
                    else:
                        other_chunks.append(chunk)

                chunks = lab_chunks + other_chunks
            else:
                chunks = retrieved_chunks

        if not chunks:
            if verbose:
                print(f"[RETRIEVAL] Course retrieval failed, trying semantic search\n")

            try:
                query_embedding = self.ollama.embed_single(query_text)
                chunks = self.vector_db.search(
                    query_embedding=query_embedding,
                    top_k=10
                )
            except Exception as e:
                if verbose:
                    print(f"  Semantic search failed: {e}\n")
                chunks = []

        if verbose:
            print(f"[RETRIEVAL] Retrieved {len(chunks)} chunks\n")

        if not chunks:
            return {
                "query": query_text,
                "answer": "Not in syllabus.",
                "method": "semantic" if not resolved_course_code else "exhaustive",
                "chunks_retrieved": 0,
                "chunks_used": 0,
                "llm_used": False,
                "processing_time": 0.01
            }

        context, chunks_used = self._build_safe_context(chunks, self.max_context_chars)

        if verbose:
            print(f"[LLM EXTRACTION]")
            print(f"  Context: {len(context)} chars from {chunks_used} chunks\n")

        prompt = self._build_minimal_prompt(query_text, context)

        try:
            raw_answer = self._generate_with_timeout(prompt)

            validated_answer = self._validate_answer(raw_answer, context, query_text)

            if verbose and raw_answer != validated_answer:
                print(f"[VALIDATION] Answer failed grounding check - returning 'Not in syllabus.'\n")

            answer = validated_answer
        except Exception as e:
            answer = f"Error: {str(e)}"

        return {
            "query": query_text,
            "answer": answer,
            "method": "semantic" if not resolved_course_code else "exhaustive",
            "chunks_retrieved": len(chunks),
            "chunks_used": chunks_used,
            "llm_used": True,
            "processing_time": 0.5
        }

    def _generate_with_timeout(self, prompt: str) -> str:
        try:
            response = requests.post(
                self.ollama.generate_endpoint,
                json={
                    "model": self.ollama.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 300,
                        "num_ctx": 2048,
                    }
                },
                timeout=45
            )

            if response.status_code == 200:
                return response.json()['response'].strip()
            else:
                return f"Error: HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            return "Error: LLM timeout"
        except Exception as e:
            return f"Error: {str(e)}"


class InteractiveInterface:
    """
    Interactive CLI interface with department selection and SESSION SUPPORT.

    Flow:
      1. Session is created.
      2. User is prompted to select a department (blocks until valid input).
      3. Queries are accepted normally.
    """

    def __init__(self, rag_system: AcademicRAGSystem):
        self.rag = rag_system

        if self.rag.session_manager:
            self.session = self.rag.session_manager.create_session()
            self.session_id = self.session.session_id
            print(f"✓ Session created: {self.session_id[:8]}...\n")
        else:
            self.session_id = None

    def _prompt_department(self) -> None:
        """
        Prompt the user to select a department before any queries can run.
        Blocks until a valid department is entered or the user quits.
        """
        available = self.rag.get_available_departments()

        print("=" * 70)
        if available:
            print(f"Available departments: {', '.join(available)}")
        else:
            print("No departments found on disk. Enter a department code manually.")
        print("=" * 70)

        while True:
            try:
                raw = input("Select department (e.g., CSE, ECE, EEE): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n👋 Goodbye!\n")
                raise SystemExit(0)

            if not raw:
                continue

            if raw.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!\n")
                raise SystemExit(0)

            result = self.rag.set_department(raw, session_id=self.session_id)
            if result["ok"]:
                print(f"✓ Department set to {result['department']}\n")
                return
            else:
                print(f"❌ {result['error']}")

    def run(self):
        # Department must be selected before any queries
        self._prompt_department()

        print("\n" + "=" * 70)
        print("INTERACTIVE QUERY MODE (v4.2)")
        print("=" * 70)
        print("\nCommands:")
        print("  <your question>    - Ask about the syllabus")
        print("  dept <CODE>        - Switch department (e.g., dept ECE)")
        print("  session            - Show session info")
        print("  quit / exit        - Exit")
        print("\nExamples:")
        print("  What is the course code for DevOps?")
        print("  unit 1             (follows previous course)")
        print("  ge3151 and ge3152 syllabus")
        print("  Compare credits of OOP + OOP Lab")
        print("=" * 70 + "\n")

        while True:
            try:
                user_input = input("📚 Query> ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!\n")
                    break

                if user_input.lower() == 'session':
                    if self.session_id and self.rag.session_manager:
                        info = self.rag.session_manager.get_session_info(self.session_id)
                        print(f"\n{info}\n")
                    else:
                        print("\nNo session manager enabled\n")
                    continue

                # dept switch command
                dept_match = re.match(r'^dept\s+(\S+)$', user_input, re.IGNORECASE)
                if dept_match:
                    result = self.rag.set_department(dept_match.group(1), session_id=self.session_id)
                    if result["ok"]:
                        print(f"✓ Switched to department {result['department']}\n")
                    else:
                        print(f"❌ {result['error']}\n")
                    continue

                result = self.rag.query(
                    user_input,
                    verbose=True,
                    session_id=self.session_id
                )

                print("─" * 70)
                print("ANSWER:")
                print("─" * 70)
                print(result['answer'])
                print("─" * 70)
                print(f"Method: {result['method']} | Retrieved: {result['chunks_retrieved']} | LLM: {result['llm_used']}")
                print("=" * 70 + "\n")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!\n")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


def main():
    # Construct system without a hard-coded department.
    # The CLI will prompt the user for one before accepting queries.
    rag = AcademicRAGSystem(
        department=None,          # No default; user selects at runtime
        persist_path="./vector_db",
        max_context_chars=1500,
        enable_sessions=True
    )

    interface = InteractiveInterface(rag)
    interface.run()


if __name__ == "__main__":
    main() 