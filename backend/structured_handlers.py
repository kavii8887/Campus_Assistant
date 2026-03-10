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

def handle_credits(
    course_code: Optional[str],
    course_name: Optional[str],
    resolver,
    query: str,
    last_ambiguities: List[Tuple[str, str]],
) -> Tuple[str, List[Tuple[str, str]]]:
    """BUG FIX 6: More conversational responses."""
    if course_code:
        credits = resolver.get_credits_from_code(course_code)
        name = resolver.get_name_from_code(course_code) or course_name or course_code
        if credits:
            return f"{name} ({course_code}) is worth {credits} credits.", []
        return f"I couldn't find credit information for {course_code}.", []

    # Try to resolve code manually
    detected_code, detected_name, ambiguities = resolver.resolve_code(query, allow_fuzzy=True)

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
        credits = resolver.get_credits_from_code(detected_code)
        actual_name = resolver.get_name_from_code(detected_code) or detected_name
        if credits:
            return f"{actual_name} ({detected_code}) is worth {credits} credits.", []
        return f"I couldn't find credit information for {detected_code}.", []

    return "Which course's credits would you like to know?", []


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


def handle_credits_compare(query: str, resolver, semester_num: Optional[int] = None, verbose: bool = False) -> str:
    """Handle multi-course credit comparison and semester aggregations."""
    if semester_num:
        courses = resolver.get_courses_by_semester(semester_num)
        if not courses:
            return f"I couldn't find any courses for semester {semester_num}."
    else:
        courses = resolver.resolve_multiple_codes(query)

        if len(courses) < 2:
            if verbose:
                print(f"  Primary resolution found {len(courses)} courses, trying acronym scan...")
            courses = _scan_acronyms_for_credits(query, resolver)

        if len(courses) < 2:
            return "Please specify two courses to compare credits. For example: 'compare credits of OOP and OOP Lab'"

    q = query.lower()
    if "total" in q or "sum" in q or semester_num:
        total = 0
        for code, name in courses:
            cstr = resolver.get_credits_from_code(code)
            if cstr:
                try:
                    total += int(cstr.split('-')[0])
                except ValueError:
                    pass
        if semester_num:
            return f"Total credits for Semester {semester_num}: {total}\n\nCourses included:\n" + "\n".join(
                [f"• {name} ({code}): {resolver.get_credits_from_code(code) or 0}" for code, name in courses]
            )
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
    staff_vdb,
    query_embedding: List[float],
    resolver,
    session_course: Optional[str] = None
) -> str:
    """
    RAG-driven staff lookup (NO LLM inference).
    Performs quick semantic retrieval and formats the results gracefully.
    """
    if staff_vdb is None:
        return "Staff directory isn't available for this department right now."
    
    q = query.lower()
    
    # Check if this is a specific lookup vs a generic list query
    import re
    is_list_query = bool(re.search(r'\b(list|show|all)\b.*\b(faculty|staff[s]?|professors?|instructors?|lecturers?)\b', q))
    is_hod_query = any(t in q for t in ['hod', 'head of department', 'head of the department'])
    
    # Retrieve closest staff profiles
    top_k_val = 50 if is_list_query else 3
    chunks = staff_vdb.search(query_embedding, top_k=top_k_val)
    
    if is_hod_query:
        # Find the chunk that actually mentions HOD/Head
        hod_chunk = None
        for c in chunks:
            desig = c.get('metadata', {}).get('designation', '').lower()
            if 'head' in desig or 'hod' in desig:
                hod_chunk = c
                break
        
        # Fallback to the top score if designation wasn't parsed correctly
        if not hod_chunk and chunks:
            hod_chunk = chunks[0]
            
        if hod_chunk:
            metadata = hod_chunk.get('metadata', {})
            name = metadata.get('staff_name', 'Unknown')
            desig = metadata.get('designation', 'Professor')
            dept = metadata.get('department', '')
            
            return f"The Head of the Department for {dept} is {name} ({desig}).\n\nContact: {metadata.get('email', 'N/A')}"

    # Default to a summarized single-result response for non-list questions to mimic LLM behavior
    if not is_list_query and chunks:
        c = chunks[0]
        metadata = c.get('metadata', {})
        name = metadata.get('staff_name', 'Unknown')
        desig = metadata.get('designation', 'Faculty')
        dept = metadata.get('department', '')
        
        ans = f"{name} is a {desig} in the {dept} department."
        if metadata.get('email'):
            ans += f"\nEmail: {metadata['email']}"
        return ans

    # If it's a list query, return the directory view
    lines = ["FACULTY DIRECTORY", "=" * 60, ""]
    
    for c in chunks:
        if c.get('score', 0) < 0.4:  
            continue
            
        metadata = c.get('metadata', {})
        name = metadata.get('staff_name', 'Unknown')
        
        line = f"• {name}"
        if metadata.get('designation'):
            line += f" — {metadata['designation']}"
        if metadata.get('email'):
            line += f"\n  Email: {metadata['email']}"
            
        lines.append(line)
        lines.append("")
        
    if len(lines) == 3: 
        return "I couldn't find any relevant staff matching your query."
        
    return "\n".join(lines).strip()


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