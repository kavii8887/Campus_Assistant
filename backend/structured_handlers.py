"""
structured_handlers.py — Deterministic answer builders
=======================================================
All handlers here return plain strings with NO LLM involvement.

Version: 1.2 (Bug fixes: Conversational responses)
"""

from typing import Optional, List, Tuple, Dict, Any
import re


# ── StructuredAcademicStore handlers ─────────────────────────────────────────

def handle_objectives(course_code: str, store) -> str:
    """Return course objectives from StructuredAcademicStore."""
    if store is None:
        return "Structured store not available."

    result = store.get_objectives(course_code)
    if not result or not result.objectives:
        return f"I couldn't find course objectives for {course_code}."

    lines = [f"COURSE OBJECTIVES — {course_code}", "=" * 60, ""]
    for i, obj in enumerate(result.objectives, 1):
        lines.append(f"  {i}. {obj}")
    return "\n".join(lines)


def handle_outcomes(course_code: str, store) -> str:
    """Return course outcomes from StructuredAcademicStore."""
    if store is None:
        return "Structured store not available."

    result = store.get_outcomes(course_code)
    if not result or not result.outcomes:
        return f"I couldn't find course outcomes for {course_code}."

    lines = [f"COURSE OUTCOMES — {course_code}", "=" * 60, ""]
    for i, outcome in enumerate(result.outcomes, 1):
        if isinstance(outcome, dict):
            co_id = outcome.get('id', f"CO{i}")
            desc = outcome.get('description', '')
            lines.append(f"  {co_id}: {desc}")
        else:
            lines.append(f"  CO{i}: {outcome}")
    return "\n".join(lines)


def handle_textbooks(course_code: str, store) -> str:
    """Return course textbooks from StructuredAcademicStore."""
    if store is None:
        return "Structured store not available."

    result = store.get_textbooks(course_code)
    if not result or not result.textbooks:
        return f"I couldn't find textbooks for {course_code}."

    lines = [f"TEXTBOOKS — {course_code}", "=" * 60, ""]
    for i, tb in enumerate(result.textbooks, 1):
        line = f"  {i}. {tb.title}"
        if tb.authors:
            line += f" — {tb.authors}"
        if tb.edition:
            line += f", {tb.edition}"
        if tb.publisher:
            line += f", {tb.publisher}"
        if tb.year:
            line += f" ({tb.year})"
        lines.append(line)
    return "\n".join(lines)


def handle_references(course_code: str, store) -> str:
    """Return course references from StructuredAcademicStore."""
    if store is None:
        return "Structured store not available."

    result = store.get_references(course_code)
    if not result or not result.references:
        return f"I couldn't find references for {course_code}."

    lines = [f"REFERENCES — {course_code}", "=" * 60, ""]
    for i, ref in enumerate(result.references, 1):
        line = f"  {i}. {ref.title}"
        if ref.authors:
            line += f" — {ref.authors}"
        if ref.edition:
            line += f", {ref.edition}"
        if ref.publisher:
            line += f", {ref.publisher}"
        if ref.year:
            line += f" ({ref.year})"
        lines.append(line)
    return "\n".join(lines)


def handle_lab_exercises(course_code: str, store) -> str:
    """Return lab exercises from StructuredAcademicStore."""
    if store is None:
        return "Structured store not available."

    result = store.get_lab_exercises(course_code)
    if not result or not result.exercises:
        return f"I couldn't find lab exercises for {course_code}."

    lines = [f"LAB EXERCISES — {course_code}", "=" * 60, ""]
    for ex in result.exercises:
        line = f"  {ex.number}. {ex.title}"
        if ex.description:
            line += f"\n     {ex.description}"
        lines.append(line)
    return "\n".join(lines)


def handle_unit_list(course_code: str, store) -> str:
    """Return unit list from StructuredAcademicStore."""
    if store is None:
        return "Structured store not available."

    units = store.get_units(course_code)
    if not units:
        return f"I couldn't find the unit structure for {course_code}."

    lines = [f"UNITS — {course_code}", "=" * 60, ""]
    for u in units:
        line = f"  Unit {u.unit_number}: {u.unit_title}"
        if u.hours:
            line += f"  ({u.hours} hrs)"
        lines.append(line)
    return "\n".join(lines)


# ── CourseCodeResolver handlers (BUG FIX 6) ──────────────────────────────────

def handle_credits(course_code: Optional[str], resolver) -> str:
    """BUG FIX 6: More conversational responses."""
    if not course_code:
        return "Which course's credits would you like to know?"
    
    credits = resolver.get_credits_from_code(course_code)
    name = resolver.get_name_from_code(course_code) or course_code
    
    if credits:
        return f"{name} ({course_code}) is worth {credits} credits."
    
    return f"I couldn't find credit information for {course_code}."


def handle_course_name(course_code: Optional[str], resolver) -> str:
    """BUG FIX 6: More conversational responses."""
    if not course_code:
        return "Which course would you like to know the name of?"
    
    name = resolver.get_name_from_code(course_code)
    if name:
        return f"{course_code} is {name}."
    
    return f"I don't have {course_code} in my database. Could you check the course code?"


def handle_course_code(
    course_code: Optional[str],
    course_name: Optional[str],
    resolver,
    query: str,
    last_ambiguities: List[Tuple[str, str]],
) -> Tuple[str, List[Tuple[str, str]]]:
    """
    Returns (answer_string, updated_last_ambiguities).
    last_ambiguities is non-empty only when disambiguation is needed.
    """
    # Pipeline already resolved a code
    if course_code:
        name = resolver.get_name_from_code(course_code) or course_name or "Unknown"
        return f"The course code for {name} is {course_code}.", []

    # Try to extract course name from query and re-resolve
    course_name_query = _extract_course_name_for_code_query(query)
    detected_code, detected_name, ambiguities = resolver.resolve_code(course_name_query, allow_fuzzy=False)

    if ambiguities:
        unique: Dict[str, str] = {}
        for amb in ambiguities:
            code = amb.split('(')[1].rstrip(')')
            name = amb.split('(')[0].strip()
            unique[code] = name
        new_ambs = list(unique.items())
        msg = "I found multiple courses. Could you be more specific or enter a number?\n" + "\n".join(
            f"{i + 1}. {n} ({c})" for i, (c, n) in enumerate(new_ambs)
        )
        return msg, new_ambs

    if detected_code:
        actual_name = resolver.get_name_from_code(detected_code) or detected_name
        return f"The course code for {actual_name} is {detected_code}.", []

    return "I couldn't find that course in the database. Could you check the course name?", []


def handle_credits_compare(query: str, resolver, verbose: bool = False) -> str:
    """Handle multi-course credit comparison."""
    courses = resolver.resolve_multiple_codes(query)

    if len(courses) < 2:
        if verbose:
            print(f"  Primary resolution found {len(courses)} courses, trying acronym scan...")
        courses = _scan_acronyms_for_credits(query, resolver)

    if len(courses) < 2:
        return "Please specify two courses to compare credits. For example: 'compare credits of OOP and OOP Lab'"

    q = query.lower()
    if "total" in q or "sum" in q:
        total = 0
        for code, name in courses:
            cstr = resolver.get_credits_from_code(code)
            if cstr:
                try:
                    total += int(cstr.split('-')[0])
                except ValueError:
                    pass
        return f"Total credits: {total}"

    lines = []
    for code, name in courses:
        credits = resolver.get_credits_from_code(code)
        if credits:
            lines.append(f"{name} ({code}): {credits} credits")
        else:
            lines.append(f"{name} ({code}): Credits not available")
    return "\n".join(lines)


def _scan_acronyms_for_credits(
    query: str,
    resolver,
) -> List[Tuple[str, str]]:
    """Fallback: scan query word-by-word for acronym matches."""
    words = query.upper().split()
    results = []
    seen = set()

    for word in words:
        if word in resolver.acronym_to_code:
            code = resolver.acronym_to_code[word]
            if code not in seen:
                name = resolver.get_name_from_code(code)
                results.append((code, name))
                seen.add(code)

    for i in range(len(words) - 1):
        two = f"{words[i]} {words[i + 1]}"
        if two in resolver.acronym_to_code:
            code = resolver.acronym_to_code[two]
            if code not in seen:
                name = resolver.get_name_from_code(code)
                results.append((code, name))
                seen.add(code)

    return results


# ── Vector DB handlers (BUG FIX 6) ───────────────────────────────────────────

def handle_unit_content(
    course_code: Optional[str],
    unit_number: Optional[str],
    vector_db,
) -> str:
    """BUG FIX 6: More conversational responses."""
    if not course_code:
        return "Which course's unit content would you like to see?"
    
    if not unit_number:
        return "Which unit would you like to see? (Specify like 'unit 1' or 'unit I')"

    chunks = vector_db.retrieve_by_course(
        course_code=course_code,
        unit_number=unit_number,
        top_k=50
    )
    
    if not chunks:
        return f"I couldn't find Unit {unit_number} content for {course_code}. The unit might not be in the uploaded syllabus."

    sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])
    lines = ["=" * 70, f"COURSE: {course_code} | UNIT: {unit_number}", "=" * 70, ""]
    for chunk in sorted_chunks:
        lines.append(chunk['text'])
        lines.append("")
    return "\n".join(lines)


def handle_full_syllabus(
    course_code: Optional[str],
    query: str,
    resolver,
    vector_db,
    ollama,
    last_ambiguities: List[Tuple[str, str]],
) -> Tuple[str, Optional[str], List[Tuple[str, str]]]:
    """
    Returns (answer, resolved_course_code, updated_last_ambiguities).
    resolved_course_code is set so callers can update session.
    """
    if not course_code:
        course_name_query = _extract_syllabus_course(query)
        multi = resolver.resolve_multiple_codes(course_name_query)
        if len(multi) > 1:
            new_ambs = multi
            msg = "I found multiple courses. Which one would you like? Enter a number:\n" + "\n".join(
                f"{i + 1}. {n} ({c})" for i, (c, n) in enumerate(new_ambs)
            )
            return msg, None, new_ambs

        detected_code, _, ambiguities = resolver.resolve_code(course_name_query, allow_fuzzy=False)
        if ambiguities:
            unique: Dict[str, str] = {}
            for amb in ambiguities:
                code = amb.split('(')[1].rstrip(')')
                name = amb.split('(')[0].strip()
                unique[code] = name
            new_ambs = list(unique.items())
            msg = "I found multiple courses. Which one would you like? Enter a number:\n" + "\n".join(
                f"{i + 1}. {n} ({c})" for i, (c, n) in enumerate(new_ambs)
            )
            return msg, None, new_ambs

        if not detected_code:
            return "I couldn't find that course. Could you specify the course code or name?", None, []
        course_code = detected_code

    chunks = vector_db.retrieve_by_course(course_code=course_code, top_k=200)

    if not chunks and ollama:
        try:
            qe = ollama.embed_single(_extract_syllabus_course(query))
            chunks = vector_db.search(query_embedding=qe, top_k=200)
        except Exception:
            chunks = []

    if not chunks:
        return f"I couldn't find the syllabus for {course_code}.", course_code, []

    sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])
    lines = ["=" * 70, f"COURSE: {course_code}", "=" * 70 + "\n"]
    for chunk in sorted_chunks:
        lines.append(chunk['text'])
        lines.append("")
    return "\n".join(lines), course_code, []


def handle_full_syllabus_multi(query: str, resolver, vector_db) -> str:
    """Aggregate full syllabus for multiple courses, no LLM."""
    courses = resolver.resolve_multiple_codes(query)
    if len(courses) < 2:
        return ""

    parts = []
    for code, name in courses:
        chunks = vector_db.retrieve_by_course(course_code=code, top_k=200)
        if chunks:
            sorted_chunks = sorted(chunks, key=lambda c: c['metadata']['chunk_index'])
            section = ["=" * 70, f"COURSE: {code} — {name}", "=" * 70, ""]
            for chunk in sorted_chunks:
                section.append(chunk['text'])
                section.append("")
            parts.append("\n".join(section))
        else:
            parts.append(f"I couldn't find the syllabus for {name} ({code}).")
    return "\n\n".join(parts)


# ── Staff info handler ────────────────────────────────────────────────────────

def handle_staff_query(
    query: str,
    course_code: Optional[str],
    staff_data: Optional[Dict],
    resolver,
    session_course: Optional[str] = None
) -> str:
    """
    Deterministic staff lookup (NO LLM).
    NOW supports session context for "this course" references.
    """
    if staff_data is None or not staff_data.get('staff'):
        return "Staff data isn't available right now."
    
    q = query.lower()
    
    # ── Detect query intent ───────────────────────────────────────────────────
    is_list_dept_faculty = any(t in q for t in ['list faculty', 'list staff', 'faculty in', 'staff in', 'professors in'])
    is_who_teaches = any(t in q for t in ['who teaches', 'who is teaching', 'instructor for', 'professor for', 'faculty for'])
    is_this_course = any(t in q for t in ['this course', 'this subject', 'it'])
    
    # ── Department list query ─────────────────────────────────────────────────
    if is_list_dept_faculty:
        dept_match = None
        for dept in ['CSE', 'ECE', 'EEE', 'MECH', 'CIVIL', 'IT']:
            if dept.lower() in q:
                dept_match = dept
                break
        
        if not dept_match:
            return "Which department's faculty would you like to see? (e.g., CSE, ECE, EEE)"
        
        faculty = [s for s in staff_data['staff'] if s.get('department', '').upper() == dept_match]
        
        if not faculty:
            return f"I don't have staff data for {dept_match} department."
        
        lines = [f"FACULTY — {dept_match} DEPARTMENT", "=" * 60, ""]
        for s in faculty:
            line = f"• {s.get('name', 'Unknown')}"
            if s.get('designation'):
                line += f" — {s['designation']}"
            if s.get('email'):
                line += f"\n  Email: {s['email']}"
            if s.get('subjects'):
                subj_names = []
                for code in s['subjects']:
                    name = resolver.get_name_from_code(code)
                    subj_names.append(f"{name} ({code})" if name else code)
                line += f"\n  Teaches: {', '.join(subj_names)}"
            lines.append(line)
        
        return "\n".join(lines)
    
    # ── Who teaches course query ──────────────────────────────────────────────
    if is_who_teaches or course_code or is_this_course:
        target_code = course_code
        
        if not target_code and is_this_course and session_course:
            target_code = session_course
        
        if not target_code:
            target_code = _extract_course_code_from_query(query)
        
        if not target_code:
            code, name, _ = resolver.resolve_code(query, allow_fuzzy=False)
            if code:
                target_code = code
        
        if not target_code:
            return "Which course are you asking about?"
        
        instructors = [
            s for s in staff_data['staff']
            if target_code.upper() in [c.upper() for c in s.get('subjects', [])]
        ]
        
        if not instructors:
            course_name = resolver.get_name_from_code(target_code)
            return f"I don't have instructor information for {course_name or target_code}."
        
        course_name = resolver.get_name_from_code(target_code) or target_code
        lines = [f"INSTRUCTORS — {course_name} ({target_code})", "=" * 60, ""]
        
        for s in instructors:
            line = f"• {s.get('name', 'Unknown')}"
            if s.get('designation'):
                line += f" — {s['designation']}"
            if s.get('email'):
                line += f"\n  Email: {s['email']}"
            if s.get('department'):
                line += f"\n  Department: {s['department']}"
            if s.get('area_of_specialization'):
                line += f"\n  Specialization: {s['area_of_specialization']}"
            lines.append(line)
        
        return "\n".join(lines)
    
    return "What staff information would you like? (e.g., 'who teaches GE3151' or 'list faculty in CSE')"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _extract_course_name_for_code_query(query: str) -> str:
    q = query.lower()
    patterns = [
        r'course\s+code\s+(?:for|of)\s+(.+)$',
        r'code\s+(?:for|of)\s+(.+)$',
        r"what(?:'s| is)\s+the\s+(?:course\s+)?code\s+(?:for|of)?\s*(.+)$",
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            extracted = m.group(1).strip()
            if extracted:
                return extracted
    suffix = re.search(r'^(.+?)\s+course\s+code\s*$', q)
    if suffix:
        ex = suffix.group(1).strip()
        if ex not in {'what', 'what is', "what's", 'whats', 'the'}:
            return ex
    return query


def _extract_syllabus_course(query: str) -> str:
    q = query.lower()
    patterns = [
        r'syllabus\s+(?:for|of)\s+(.+)$',
        r'full\s+syllabus\s+(?:for|of)\s+(.+)$',
        r'(?:give|show)\s+(?:me\s+)?(?:the\s+)?syllabus\s+(?:for|of)\s+(.+)$',
    ]
    for pattern in patterns:
        m = re.search(pattern, q)
        if m:
            return m.group(1).strip()
    return query


def _extract_course_code_from_query(query: str) -> Optional[str]:
    """Extract course code from query string."""
    for p in [r'\b([A-Z]{2,4})\s*(\d{3,5})\b', r'\b([A-Z]{3})(\d{3})\b']:
        m = re.search(p, query, re.IGNORECASE)
        if m:
            return f"{m.group(1)}{m.group(2)}".upper()
    return None