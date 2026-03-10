"""
routing.py — Query classification & routing decisions
======================================================
Single source of truth for "is this query structured or semantic?"

Wraps IntentParser and augments it with the legacy pattern set from
rag_runtime so nothing is regressed.

STRUCTURED query types (NO LLM, deterministic):
  UNIT_CONTENT        → vector DB by course+unit
  FULL_SYLLABUS       → vector DB by course (all units)
  FULL_SYLLABUS_MULTI → vector DB for N courses, aggregated
  COURSE_CODE         → CourseCodeResolver
  COURSE_NAME         → CourseCodeResolver
  CREDITS             → CourseCodeResolver
  CREDITS_COMPARE     → CourseCodeResolver × N courses
  OBJECTIVES          → StructuredAcademicStore
  OUTCOMES            → StructuredAcademicStore
  TEXTBOOKS           → StructuredAcademicStore
  REFERENCES          → StructuredAcademicStore
  LAB_EXERCISES       → StructuredAcademicStore
  UNIT_LIST           → StructuredAcademicStore
  ATTENDANCE_PERCENTAGE → Deterministic calculation
  ATTENDANCE_STATUS     → Deterministic calculation
  ATTENDANCE_COUNT      → Deterministic calculation

SEMANTIC query types (LLM with context):
  SEMANTIC            → vector retrieval + LLM

Version: 1.2 (Bug fix: "subject name" synonym for "course name")
"""

import re
from typing import Optional, Tuple

try:
    from intent_parser import IntentParser
    from models import QueryIntent, ParsedQuery
    _INTENT_PARSER_AVAILABLE = True
    _intent_parser = IntentParser()
except ImportError:
    _INTENT_PARSER_AVAILABLE = False
    _intent_parser = None
    QueryIntent = None
    ParsedQuery = None


# ── String constants for all query types used across runtime ─────────────────
QT_UNIT_CONTENT        = "UNIT_CONTENT"
QT_FULL_SYLLABUS       = "FULL_SYLLABUS"
QT_FULL_SYLLABUS_MULTI = "FULL_SYLLABUS_MULTI"
QT_COURSE_CODE         = "COURSE_CODE"
QT_COURSE_NAME         = "COURSE_NAME"
QT_CREDITS             = "CREDITS"
QT_CREDITS_COMPARE     = "CREDITS_COMPARE"
QT_OBJECTIVES          = "OBJECTIVES"
QT_OUTCOMES            = "OUTCOMES"
QT_TEXTBOOKS           = "TEXTBOOKS"
QT_REFERENCES          = "REFERENCES"
QT_LAB_EXERCISES       = "LAB_EXERCISES"
QT_UNIT_LIST           = "UNIT_LIST"
QT_ATTENDANCE_PERCENTAGE = "ATTENDANCE_PERCENTAGE"
QT_ATTENDANCE_STATUS   = "ATTENDANCE_STATUS"
QT_ATTENDANCE_COUNT    = "ATTENDANCE_COUNT"
QT_SEMANTIC            = "SEMANTIC"

# Query types that go to StructuredAcademicStore
STRUCTURED_STORE_TYPES = {
    QT_OBJECTIVES, QT_OUTCOMES, QT_TEXTBOOKS, QT_REFERENCES,
    QT_LAB_EXERCISES, QT_UNIT_LIST,
}

# Attendance query types (deterministic)
ATTENDANCE_TYPES = {
    QT_ATTENDANCE_PERCENTAGE, QT_ATTENDANCE_STATUS, QT_ATTENDANCE_COUNT,
}

# All structured types (no LLM)
ALL_STRUCTURED_TYPES = STRUCTURED_STORE_TYPES | ATTENDANCE_TYPES | {
    QT_UNIT_CONTENT, QT_FULL_SYLLABUS, QT_FULL_SYLLABUS_MULTI,
    QT_COURSE_CODE, QT_COURSE_NAME, QT_CREDITS, QT_CREDITS_COMPARE,
}


# ── Intent → query type mapping ──────────────────────────────────────────────
_INTENT_TO_QT = None  # built lazily after import check

def _get_intent_map():
    global _INTENT_TO_QT
    if _INTENT_TO_QT is None and _INTENT_PARSER_AVAILABLE:
        _INTENT_TO_QT = {
            QueryIntent.COURSE_NAME:       QT_COURSE_NAME,
            QueryIntent.CREDITS:           QT_CREDITS,
            QueryIntent.FULL_SYLLABUS:     QT_FULL_SYLLABUS,
            QueryIntent.UNIT_LIST:         QT_UNIT_LIST,
            QueryIntent.COURSE_OBJECTIVES: QT_OBJECTIVES,
            QueryIntent.COURSE_OUTCOMES:   QT_OUTCOMES,
            QueryIntent.TEXTBOOKS:         QT_TEXTBOOKS,
            QueryIntent.REFERENCES:        QT_REFERENCES,
            QueryIntent.UNIT_TOPICS:       QT_UNIT_CONTENT,
            QueryIntent.LAB_EXERCISES:     QT_LAB_EXERCISES,
            QueryIntent.EXPLANATION:       QT_SEMANTIC,
            QueryIntent.SUMMARY:           QT_SEMANTIC,
            QueryIntent.GENERAL:           QT_SEMANTIC,
        }
    return _INTENT_TO_QT


# ── Staff name cache for routing ─────────────────────────────────────────────
_staff_name_cache = None

def _is_staff_name_in_query(q_lo: str) -> bool:
    """Check if any known staff/admin name appears in the query."""
    global _staff_name_cache
    if _staff_name_cache is None:
        _staff_name_cache = set()
        try:
            import json
            from pathlib import Path
            p = Path("data/staffs.json")
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                # Admin names
                principal = data.get("administration", {}).get("principal", {})
                if principal.get("name"):
                    _add_name_parts(_staff_name_cache, principal["name"])
                for person in data.get("administration", {}).get("administrative_hierarchy", []):
                    if person.get("name"):
                        _add_name_parts(_staff_name_cache, person["name"])
                # Department staff names
                for dept in data.get("departments", []):
                    for s in dept.get("staff", []):
                        if s.get("name"):
                            _add_name_parts(_staff_name_cache, s["name"])
        except Exception:
            pass

    # Check if any cached name part appears in the query
    for name_part in _staff_name_cache:
        if name_part in q_lo:
            return True
    return False


def _add_name_parts(cache: set, full_name: str):
    """Add meaningful name parts (length > 2) to the cache."""
    clean = re.sub(r'[^a-z\s]', '', full_name.lower()).strip()
    for part in clean.split():
        if len(part) > 2:  # Skip initials like "a", "m", "s"
            cache.add(part)


# ── Public API ────────────────────────────────────────────────────────────────

def classify(query: str, session_course: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Classify a query into (is_structured, query_type).

    Checks deterministic triggers (staff/attendance) first.
    Then tries IntentParser (richer detection for syllabus), falls back to the
    legacy pattern set.

    Returns:
        (True, "QUERY_TYPE") for structured queries
        (False, None)        for semantic queries
    """
    q_lo = query.lower()
    
    # ── 0. High priority interceptors (Staff / Attendance) ───────────────────
    # Staff info — keyword triggers
    staff_regex = r'\b(who\s+teaches|who\s+is\s+teaching|instructor|professor[s]?|facult(?:y|ies)|staff[s]?|hod|head\s+of\s+department|email|contact\s+(?:number|details|info|no)|phone\s+(?:number|no)|principal|vice\s+principal|bursar|superintendent|administration|institution|specializ\w*|qualification|area\s+of|designation|experience\s+year|teaches?\s+what|department\s+head)\b'
    if re.search(staff_regex, q_lo):
        return True, "STAFF_INFO"

    # Staff info — known name detection (catches "Dr. Kalpana's ..." queries)
    if _is_staff_name_in_query(q_lo):
        return True, "STAFF_INFO"

    # Attendance percentage
    if any(t in q_lo for t in [
        'attendance percentage', 'my attendance', 'attendance percent',
        'what is my attendance', "what's my attendance",
    ]):
        return True, "ATTENDANCE_PERCENTAGE"
    
    # Attendance status
    if any(t in q_lo for t in [
        'eligible for exam', 'eligibility', 'attendance status',
        'can i write exam', 'exam eligibility', 'am i eligible',
    ]) and 'attendance' in q_lo:
        return True, "ATTENDANCE_STATUS"
        
    # Class count
    if any(t in q_lo for t in [
        'how many classes', 'classes attended', 'classes did i attend',
        'number of classes', 'class count',
    ]):
        return True, "ATTENDANCE_COUNT"


    # ── 1. IntentParser path ─────────────────────────────────────────────────
    if _INTENT_PARSER_AVAILABLE and _intent_parser is not None:
        parsed = _intent_parser.parse(query, session_course)
        intent_map = _get_intent_map()

        if parsed.intents:
            primary = parsed.intents[0]
            qt = intent_map.get(primary, QT_SEMANTIC)

            # Multi-course FULL_SYLLABUS upgrade
            if qt == QT_FULL_SYLLABUS:
                if _has_separator(query):
                    qt = QT_FULL_SYLLABUS_MULTI

            is_structured = qt != QT_SEMANTIC
            return is_structured, (qt if is_structured else None)

    # ── 2. Legacy pattern fallback ────────────────────────────────────────────
    return _legacy_classify(query)


def _has_separator(query: str) -> bool:
    return bool(re.search(r'\s+and\s+|\s*\+\s*|\s*,\s*|\s+vs\.?\s+', query, re.IGNORECASE))


def _legacy_classify(query: str) -> Tuple[bool, Optional[str]]:
    """
    Original _is_structured_query() logic from rag_runtime, extended with
    OBJECTIVES / OUTCOMES / TEXTBOOKS / REFERENCES / LAB_EXERCISES / UNIT_LIST
    and ATTENDANCE types.
    """
    q = query.lower()

    # ── ATTENDANCE queries (PHASE 4) ─────────────────────────────────────────
    # Attendance percentage
    if any(t in q for t in [
        'attendance percentage', 'my attendance', 'attendance percent',
        'what is my attendance', "what's my attendance",
    ]):
        return True, QT_ATTENDANCE_PERCENTAGE
    
    # Attendance status / eligibility
    if any(t in q for t in [
        'eligible for exam', 'eligibility', 'attendance status',
        'can i write exam', 'exam eligibility', 'am i eligible',
    ]) and 'attendance' in q:
        return True, QT_ATTENDANCE_STATUS
    
    # Class count
    if any(t in q for t in [
        'how many classes', 'classes attended', 'classes did i attend',
        'number of classes', 'class count',
    ]):
        return True, QT_ATTENDANCE_COUNT
    
    # Staff info
    staff_regex = r'\b(who\s+teaches|who\s+is\s+teaching|instructor|professor[s]?|facult(?:y|ies)|staff[s]?|hod|head\s+of\s+department|email|contact\s+(?:number|details|info|no)|phone\s+(?:number|no)|principal|vice\s+principal|bursar|superintendent|administration|institution)\b'
    if re.search(staff_regex, q):
        return True, "STAFF_INFO"

    # ── UNIT_CONTENT ─────────────────────────────────────────────────────────
    bare_unit = [
        r'^\s*unit\s+[IVX1-5]+\s*$',
        r'^\s*(first|second|third|fourth|fifth)\s+unit\s*$',
        r'^\s*unit\s+(first|second|third|fourth|fifth)\s*$',
    ]
    for p in bare_unit:
        if re.match(p, q):
            return True, QT_UNIT_CONTENT

    unit_with_course = [
        r'\bunit\s*[IVX1-5]+\s+(?:for|of|in)\s+\S',
        r'\b(first|second|third|fourth|fifth)\s+unit\s+(?:for|of|in)\s+\S',
        r'\bunit\s+(first|second|third|fourth|fifth)\s+(?:for|of|in)\s+\S',
    ]
    for p in unit_with_course:
        if re.search(p, q):
            return True, QT_UNIT_CONTENT

    # ── OBJECTIVES ───────────────────────────────────────────────────────────
    if any(t in q for t in [
        'objective', 'objectives', 'learning objective', 'course objective',
        'what are the objectives', 'list objectives',
    ]):
        return True, QT_OBJECTIVES

    # ── OUTCOMES ─────────────────────────────────────────────────────────────
    if any(t in q for t in [
        'outcome', 'outcomes', 'learning outcome', 'course outcome',
        'what are the outcomes', 'list outcomes',
    ]) or re.search(r'\bco\d+\b', q):
        return True, QT_OUTCOMES

    # ── TEXTBOOKS ────────────────────────────────────────────────────────────
    if any(t in q for t in [
        'textbook', 'textbooks', 'text book', 'prescribed book', 'course book',
        'study book', 'study material', 'required book',
    ]) or (re.search(r'\bbook', q) and not re.search(r'reference', q)):
        return True, QT_TEXTBOOKS

    # ── REFERENCES ───────────────────────────────────────────────────────────
    if any(t in q for t in [
        'reference', 'references', 'reference book', 'additional reading',
        'recommended book', 'refer book',
    ]) or re.search(r'\brefs?\b', q):
        return True, QT_REFERENCES

    # ── LAB_EXERCISES ────────────────────────────────────────────────────────
    if any(t in q for t in [
        'lab exercise', 'lab exercises', 'practical exercise', 'list of exercises',
        'lab work', 'lab program', 'list exercises',
    ]):
        return True, QT_LAB_EXERCISES

    # ── UNIT_LIST ────────────────────────────────────────────────────────────
    if any(t in q for t in [
        'list units', 'show units', 'what are the units', 'unit names',
        'unit titles', 'how many units',
    ]):
        return True, QT_UNIT_LIST

    # ── CREDITS_COMPARE (Includes Semester Aggregates) ───────────────────────
    has_credit = any(t in q for t in ['credit', 'cerdit', 'creadit'])
    has_sep = _has_separator(q)
    has_compare = any(t in q for t in ['compare', 'comparison'])
    sem = [r'\bsem(?:e)?ster\s+[1-8ivx]+\b', r'\bsem\s+[1-8ivx]+\b', r'\b[1-8ivx]+(?:st|nd|rd|th)?\s+sem(?:e)?ster\b']
    has_semester = any(re.search(p, q) for p in sem)
    
    if has_credit and (has_compare or has_sep or has_semester):
        return True, QT_CREDITS_COMPARE

    # ── COURSE_CODE ──────────────────────────────────────────────────────────
    if any(t in q for t in [
        'course code for', 'code for', 'course code of', 'code of',
        'what is the course code', 'what is the code',
        "what's the course code", "what's the code",
    ]):
        return True, QT_COURSE_CODE
    if re.search(r'.+\s+course\s+code\s*$', q):
        return True, QT_COURSE_CODE

    # ── COURSE_NAME / SUBJECT_NAME (BUG FIX 3) ───────────────────────────────
    if any(t in q for t in [
        'course name', 'name of the course', 'name of course',
        'course title', 'title of the course', 'title of course',
        'subject name', 'name of the subject', 'name of subject',  # ← ADDED
        'subject title', 'title of the subject',  # ← ADDED
    ]):
        return True, QT_COURSE_NAME

    # ── CREDITS (single) ─────────────────────────────────────────────────────
    if has_credit:
        return True, QT_CREDITS

    # ── FULL_SYLLABUS ────────────────────────────────────────────────────────
    if any(t in q for t in [
        'syllabus', 'full syllabus', 'entire syllabus', 'complete syllabus',
        'whole syllabus', 'give me the syllabus',
    ]):
        if _has_separator(q):
            return True, QT_FULL_SYLLABUS_MULTI
        return True, QT_FULL_SYLLABUS

    return False, None