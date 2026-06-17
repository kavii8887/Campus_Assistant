# pylint: disable=all
# type: ignore
"""
timetable_pipeline.py — Timetable RAG Pipeline (Year-Aware Deterministic Search)
==================================================================================
Architecture:
  1. Extract PDF → detect year-sections (each schedule grid = one year)
  2. Cache each year separately as JSON (re-extract only when PDF changes)
  3. Deterministic Python keyword search for retrieval (NO embeddings)
  4. LLM used ONLY for natural-language formatting on full-context fallback

The PDF structure (e.g. CSE_timetable.pdf):
  - Multiple pages, each year-section has:
    a) A weekly schedule grid (header row starts with "Day/Period")
    b) A subject-mapping table (header row starts with "SUB CODE" / "SUBCODE")
  - Subject mapping tables come in two flavours:
    * Lab details: [SUBCODE, SUBJECTNAME, STAFFINCHARGE, ASSISTSTAFF, VENUE]
    * Theory details: [SUBCODE, SUBJECTNAME, STAFFINCHARGE, SUBCODE2, SUBJECTNAME2, STAFFINCHARGE2]

Version: 2.0 — Year-aware multi-section parsing
"""

import json

import re
import hashlib
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


# ── Abbreviation map: short names used in the grid → searchable keywords ──────
_ABBREV_MAP = {
    "DBMS": "Database Management Systems",
    "AIML": "Artificial Intelligence and Machine Learning",
    "ALG": "Algorithms",
    "OS": "Operating Systems",
    "TOC": "Theory of Computation",
    "EVS": "Environmental Sciences and Sustainability",
    "DEVOPS": "DevOps",
    "CLOUD": "Cloud Services Management",
    "OOSE": "Object Oriented Software Engineering",
    "IOT": "Embedded Systems and IoT",
    "SOFT": "Soft Computing",
    "MULTI": "Multimedia Data Compression and Storage",
    "HST": "History of Science and Technology in India",
    "LIB": "Library",
    "MORAL": "Moral and Ethics",
}


class TimetablePipeline:

    def __init__(self, ollama_client, department: str = "CSE",
                 pdf_dir: str = "data/general/timetables",
                 cache_dir: str = "data/cache",
                 year: Optional[int] = None):
        self.ollama = ollama_client
        self.department = department.upper()
        self.pdf_dir = Path(pdf_dir)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.target_year = year  # None = load all years

        # In-memory data for the ACTIVE year
        self.daily_schedule: Dict[str, List[Dict]] = {}
        self.practicals: List[Dict] = []
        self.subject_map: Dict[str, Dict] = {}   # abbrev → {code, name, staff, ...}
        self.full_context: str = ""
        self.period_headers: List[str] = []

        # All years data (for year switching without re-parse)
        self._all_years: Dict[int, Dict] = {}

        self._load()

    # ─── LOAD ─────────────────────────────────────────────────────────────────

    def _load(self):
        """Load timetable data. Use JSON cache if PDF hasn't changed."""
        pdf_path = self._find_pdf()
        if not pdf_path:
            print(f"⚠ No timetable PDF found for {self.department} in {self.pdf_dir}")
            return

        cache_path = self.cache_dir / f"{self.department}_timetable_v2.json"
        hash_path = self.cache_dir / f"{self.department}_timetable_v2.hash"

        current_hash = self._file_hash(pdf_path)
        cached_hash = hash_path.read_text().strip() if hash_path.exists() else ""

        if cache_path.exists() and current_hash == cached_hash:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._all_years = {int(k): v for k, v in data.get("years", {}).items()}
            print(f"✓ Timetable loaded from cache for {self.department} "
                  f"({len(self._all_years)} year-sections)")
        else:
            self._extract_from_pdf(str(pdf_path))
            cache_data = {"years": {str(k): v for k, v in self._all_years.items()}}
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            hash_path.write_text(current_hash)
            print(f"✓ Timetable extracted and cached for {self.department} "
                  f"({len(self._all_years)} year-sections)")

        self._activate_year(self.target_year)

    def _activate_year(self, year: Optional[int]):
        """Activate a specific year's data, or default to best available."""
        if year and year in self._all_years:
            data = self._all_years[year]
        elif self._all_years:
            # Default: pick middle year (most useful) or first available
            available = sorted(self._all_years.keys())
            year = available[len(available) // 2] if len(available) > 1 else available[0]
            data = self._all_years[year]
        else:
            data = {}

        self.daily_schedule = data.get("daily_schedule", {})
        self.practicals = data.get("practicals", [])
        self.subject_map = data.get("subject_map", {})
        self.period_headers = data.get("period_headers", [])
        self.target_year = year
        self._build_full_context()

    def switch_year(self, year: int):
        """Switch to a different year's timetable data."""
        if year in self._all_years:
            self._activate_year(year)
            return True
        return False

    def get_available_years(self) -> List[int]:
        return sorted(self._all_years.keys())

    def _find_pdf(self) -> Optional[Path]:
        candidates = [
            self.pdf_dir / f"{self.department}_timetable.pdf",
            self.pdf_dir / f"{self.department.lower()}_timetable.pdf",
        ]
        for p in candidates:
            if p.exists():
                return p
        for p in self.pdf_dir.glob("*.pdf"):
            if self.department.lower() in p.name.lower():
                return p
        return None

    def _file_hash(self, path: Path) -> str:
        h = hashlib.md5()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    # ─── PDF EXTRACTION (Year-aware) ──────────────────────────────────────────

    def _extract_from_pdf(self, pdf_path: str):
        """Extract tables from PDF, grouping into year-sections."""
        import pdfplumber

        print(f"  Extracting from PDF: {pdf_path}")

        # Collect all tables across all pages, in order
        all_tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) >= 2:
                        all_tables.append(table)

        # Group tables into year-sections
        # A year-section starts with a schedule grid (header contains "Day/Period")
        # followed by one or more subject-mapping tables
        year_sections = []
        current_section = {"grids": [], "mappings": []}

        for table in all_tables:
            header = [self._clean_cell(c) for c in table[0]]
            header_joined = " ".join(header).upper()

            if "DAY" in header_joined and "PERIOD" in header_joined:
                # This is a schedule grid — starts a new section if we have data
                if current_section["grids"]:
                    year_sections.append(current_section)
                    current_section = {"grids": [], "mappings": []}
                current_section["grids"].append(table)
            elif "SUBCODE" in header_joined.replace(" ", "") or "SUB CODE" in header_joined:
                # This is a subject-mapping table
                current_section["mappings"].append(table)

        # Don't forget the last section
        if current_section["grids"]:
            year_sections.append(current_section)

        # Assign year numbers (II, III, IV → 2, 3, 4)
        # Heuristic: sections appear in order, starting from year 2
        for idx, section in enumerate(year_sections):
            year_num = idx + 2  # II year = 2, III year = 3, IV year = 4

            daily_schedule = {}
            period_headers = []
            practicals = []
            subject_map = {}

            # Parse schedule grids
            for grid in section["grids"]:
                sched, headers = self._parse_weekly_grid(grid)
                daily_schedule.update(sched)
                if headers and not period_headers:
                    period_headers = headers

            # Parse subject-mapping tables
            for mapping in section["mappings"]:
                labs, theories = self._parse_subject_mapping(mapping)
                practicals.extend(labs)
                for entry in theories:
                    abbrev = self._find_abbreviation(entry.get("name", ""))
                    if abbrev:
                        subject_map[abbrev] = entry
                for entry in labs:
                    abbrev = self._find_abbreviation(entry.get("name", ""))
                    if abbrev:
                        subject_map[abbrev] = entry

            # Build abbreviation map from subjects found in the grid
            for day_slots in daily_schedule.values():
                for slot in day_slots:
                    subj = slot["subject"].upper().strip()
                    if subj in _ABBREV_MAP and subj not in subject_map:
                        subject_map[subj] = {"name": _ABBREV_MAP[subj], "code": "", "staff": ""}

            self._all_years[year_num] = {
                "daily_schedule": daily_schedule,
                "practicals": practicals,
                "subject_map": subject_map,
                "period_headers": period_headers,
            }

            total_slots = sum(len(v) for v in daily_schedule.values())
            print(f"  Year {year_num}: {total_slots} slots, "
                  f"{len(practicals)} practicals, {len(subject_map)} subjects")

    def _clean_cell(self, cell) -> str:
        if not cell:
            return ""
        return str(cell).replace('\n', ' ').strip()

    def _parse_weekly_grid(self, grid) -> Tuple[Dict[str, List[Dict]], List[str]]:
        """Parse a weekly schedule table into structured data."""
        if not grid or len(grid) < 2:
            return {}, []

        headers = [self._clean_cell(c) for c in grid[0]]
        period_headers = headers[1:]

        daily_schedule = {}
        valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}

        for row_idx in range(1, len(grid)):
            row = [self._clean_cell(c) for c in grid[row_idx]]
            if not row or not row[0]:
                continue

            day = row[0].upper().strip()
            if day not in valid_days:
                continue

            day_slots = []
            col_idx = 1
            while col_idx < len(headers):
                if col_idx < len(row):
                    subject = row[col_idx]
                    period_time = headers[col_idx] if col_idx < len(headers) else ""

                    if subject:
                        # Check for lab spans: ←AIML/ALGLAB—> style
                        lab_match = re.search(r'[←<][-–—]*(.*?)[-–—]*[→>]', subject)
                        if lab_match:
                            lab_name = lab_match.group(1).strip()
                            # Lab spans multiple periods (typically 3 hours = periods 5-7 or 6-8)
                            start_period = col_idx
                            # Find how many null cells follow
                            end_period = col_idx + 1
                            while end_period < len(row) and not row[end_period]:
                                end_period += 1

                            # Build time range from start to end
                            start_time = period_time

                            day_slots.append({
                                "period": start_period,
                                "time": start_time,
                                "subject": lab_name,
                                "is_lab": True,
                                "span": end_period - start_period + 1,
                            })
                            col_idx = end_period
                            continue
                        else:
                            # Check for LUNCH BREAK header — skip
                            if "LUNCH" in period_time.upper():
                                col_idx += 1
                                continue

                            day_slots.append({
                                "period": col_idx,
                                "time": period_time,
                                "subject": subject,
                                "is_lab": False,
                                "span": 1,
                            })
                col_idx += 1

            if day_slots:
                daily_schedule[day] = day_slots

        return daily_schedule, period_headers

    def _parse_subject_mapping(self, grid) -> Tuple[List[Dict], List[Dict]]:
        """Parse a subject-mapping table. Returns (labs, theories)."""
        if not grid or len(grid) < 2:
            return [], []

        header = [self._clean_cell(c).upper().replace(" ", "") for c in grid[0]]
        num_cols = len(header)

        labs = []
        theories = []

        # Detect table type
        has_venue = any("VENUE" in h for h in header)
        has_assist = any("ASSIST" in h for h in header)

        if has_venue or has_assist:
            # Lab details table: [SUBCODE, SUBJECTNAME, STAFFINCHARGE, ASSISTSTAFF, VENUE]
            for row_idx in range(1, len(grid)):
                row = [self._clean_cell(c) for c in grid[row_idx]]
                if not row or not row[0]:
                    continue
                labs.append({
                    "code": row[0] if len(row) > 0 else "",
                    "name": row[1] if len(row) > 1 else "",
                    "staff_incharge": row[2] if len(row) > 2 else "",
                    "assistant_staff": row[3] if len(row) > 3 else "",
                    "venue": row[4] if len(row) > 4 else "",
                })
        else:
            # Theory details table: two sets of [SUBCODE, SUBJECTNAME, STAFFINCHARGE]
            for row_idx in range(1, len(grid)):
                row = [self._clean_cell(c) for c in grid[row_idx]]
                if not row or not row[0]:
                    continue

                # First triplet
                code1 = row[0] if len(row) > 0 else ""
                name1 = row[1] if len(row) > 1 else ""
                staff1 = row[2] if len(row) > 2 else ""
                if code1 and name1:
                    theories.append({"code": code1, "name": name1, "staff": staff1})

                # Second triplet (if exists)
                if num_cols >= 6:
                    code2 = row[3] if len(row) > 3 else ""
                    name2 = row[4] if len(row) > 4 else ""
                    staff2 = row[5] if len(row) > 5 else ""
                    if code2 and name2:
                        theories.append({"code": code2, "name": name2, "staff": staff2})

        return labs, theories

    def _find_abbreviation(self, name: str) -> Optional[str]:
        """Find the grid abbreviation for a full subject name."""
        name_clean = re.sub(r'[^a-z]', '', name.lower())
        for abbrev, full_name in _ABBREV_MAP.items():
            full_clean = re.sub(r'[^a-z]', '', full_name.lower())
            if full_clean and (full_clean in name_clean or name_clean in full_clean):
                return abbrev
        return None

    # ─── CONTEXT BUILDING ─────────────────────────────────────────────────────

    def _build_full_context(self):
        """Build a text representation of the active year's timetable."""
        lines = []
        year_label = f"Year {self.target_year}" if self.target_year else "All Years"
        lines.append(f"=== {self.department} DEPARTMENT TIMETABLE ({year_label}) ===\n")

        day_order = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
        for day in day_order:
            if day in self.daily_schedule:
                lines.append(f"\n--- {day} ---")
                for slot in self.daily_schedule[day]:
                    subj = slot['subject']
                    # Expand abbreviation
                    expanded = _ABBREV_MAP.get(subj.upper(), "")
                    extra = f" ({expanded})" if expanded else ""
                    lab_tag = " [LAB]" if slot.get("is_lab") else ""
                    lines.append(
                        f"  Period {slot['period']} ({slot['time']}): "
                        f"{subj}{extra}{lab_tag}"
                    )

        if self.practicals:
            lines.append("\n\n--- PRACTICAL / LAB DETAILS ---")
            for p in self.practicals:
                lines.append(
                    f"  {p['code']} | {p['name']} | Staff: {p['staff_incharge']} | "
                    f"Asst: {p['assistant_staff']} | Venue: {p['venue']}"
                )

        if self.subject_map:
            lines.append("\n\n--- SUBJECT DETAILS ---")
            for abbrev, info in self.subject_map.items():
                code = info.get("code", "")
                name = info.get("name", "")
                staff = info.get("staff", info.get("staff_incharge", ""))
                lines.append(f"  {abbrev}: {name} ({code}) — Staff: {staff}")

        self.full_context = "\n".join(lines)

    # ─── DETERMINISTIC SEARCH ─────────────────────────────────────────────────

    def _search(self, query: str) -> Tuple[str, str]:
        """Deterministic keyword search. Returns (filtered_context, search_type)."""
        q = query.lower().strip()
        results = []
        search_type = "full"

        # 0. "Now" / "current" queries — use system time
        now_keywords = ['right now', 'now', 'current period', 'current class',
                        'going on', 'happening now', 'this hour', 'current hour',
                        'at this time', 'present period', 'next period',
                        'next class', 'upcoming', 'next']
        if any(kw in q for kw in now_keywords):
            current_info = self._get_current_period()
            if current_info:
                return current_info, "realtime_now"

        # 1. Day detection
        day_map = {
            "monday": "MON", "mon": "MON", "moday": "MON",
            "tuesday": "TUE", "tue": "TUE", "tueday": "TUE",
            "wednesday": "WED", "wed": "WED",
            "thursday": "THU", "thu": "THU",
            "friday": "FRI", "fri": "FRI",
            "saturday": "SAT", "sat": "SAT",
        }

        matched_day = None
        for keyword, day_code in day_map.items():
            if keyword in q:
                matched_day = day_code
                break

        # 2. Time detection
        time_match = re.search(r'(\d{1,2})[.:](\d{2})\s*(am|pm)?', q, re.IGNORECASE)
        query_minutes = None
        if time_match:
            th, tm = int(time_match.group(1)), int(time_match.group(2))
            ampm = time_match.group(3)
            if ampm:
                ampm = ampm.upper()
            else:
                # Infer AM/PM from hour
                if 8 <= th <= 11:
                    ampm = 'AM'
                elif 1 <= th <= 5 or th == 12:
                    ampm = 'PM'

            if ampm:
                if ampm == 'PM' and th != 12:
                    th += 12
                elif ampm == 'AM' and th == 12:
                    th = 0
                query_minutes = th * 60 + tm

        # 2.5. Time + Day → find specific period
        if matched_day and query_minutes is not None and matched_day in self.daily_schedule:
            for slot in self.daily_schedule[matched_day]:
                tr = self._parse_time_range(slot['time'])
                if tr:
                    start_min, end_min = tr
                    if start_min <= query_minutes <= end_min:
                        subj = slot['subject']
                        expanded = _ABBREV_MAP.get(subj.upper(), "")
                        full_name = f" ({expanded})" if expanded else ""
                        lab_tag = " [LAB]" if slot.get("is_lab") else ""
                        result = f"{matched_day}: Period {slot['period']} ({slot['time']}): {subj}{full_name}{lab_tag}"
                        results.append(result)
                        # Add lab/practical details ONLY if the slot is a lab
                        if slot.get("is_lab"):
                            self._add_practical_info(results, subj)
                        return "\n".join(results), "time_filter"

        # 3. Day only → full day schedule
        if matched_day and matched_day in self.daily_schedule:
            search_type = "day_filter"
            results.append(f"--- {matched_day} Schedule ---")
            for slot in self.daily_schedule[matched_day]:
                subj = slot['subject']
                expanded = _ABBREV_MAP.get(subj.upper(), "")
                full_name = f" ({expanded})" if expanded else ""
                lab_tag = " [LAB]" if slot.get("is_lab") else ""
                results.append(
                    f"  Period {slot['period']} ({slot['time']}): {subj}{full_name}{lab_tag}"
                )
            # Add relevant practicals
            day_subjects = {s['subject'].upper() for s in self.daily_schedule[matched_day]}
            added_labs = set()
            for p in self.practicals:
                p_name_clean = re.sub(r'[^a-z]', '', p['name'].lower())
                for ds in day_subjects:
                    ds_clean = re.sub(r'[^a-z]', '', ds.lower())
                    if ds_clean in p_name_clean or p_name_clean in ds_clean:
                        if p['code'] not in added_labs:
                            results.append(
                                f"\n  Lab: {p['code']} | {p['name']} | "
                                f"Staff: {p['staff_incharge']} | Asst: {p['assistant_staff']} | "
                                f"Venue: {p['venue']}"
                            )
                            added_labs.add(p['code'])
            return "\n".join(results), search_type

        # 4. Subject-specific queries
        subject_matches = self._find_subject_matches(q)
        if subject_matches:
            search_type = "subject_filter"
            for match in subject_matches:
                results.append(match)
            # Also find practical details
            keywords = self._extract_keywords(q)
            for p in self.practicals:
                p_text = f"{p['code']} {p['name']}".lower()
                if any(kw in p_text for kw in keywords):
                    results.append(
                        f"Lab: {p['code']} | {p['name']} | "
                        f"Staff: {p['staff_incharge']} | Asst: {p['assistant_staff']} | "
                        f"Venue: {p['venue']}"
                    )
            if results:
                return "\n".join(results), search_type

        # 5. Staff-related queries
        if any(kw in q for kw in ['staff', 'incharge', 'in charge', 'assistant',
                                    'who teaches', 'faculty', 'instructor']):
            search_type = "staff_filter"
            for p in self.practicals:
                p_text = f"{p['code']} {p['name']} {p['staff_incharge']} {p['assistant_staff']}".lower()
                if any(kw in p_text for kw in self._extract_keywords(q)):
                    results.append(
                        f"{p['code']} | {p['name']} | Staff: {p['staff_incharge']} | "
                        f"Asst: {p['assistant_staff']} | Venue: {p['venue']}"
                    )
            if results:
                return "\n".join(results), search_type

        # 6. Venue/lab room queries
        if any(kw in q for kw in ['venue', 'lab room', 'where is', 'room', 'location']):
            search_type = "venue_filter"
            for p in self.practicals:
                p_text = f"{p['code']} {p['name']} {p['venue']}".lower()
                if any(kw in p_text for kw in self._extract_keywords(q)):
                    results.append(f"{p['code']} | {p['name']} | Venue: {p['venue']}")
            if results:
                return "\n".join(results), search_type

        # 7. Period-specific queries
        period_match = re.search(r'period\s*(\d+)', q)
        if period_match:
            search_type = "period_filter"
            period_num = int(period_match.group(1))
            for day, slots in self.daily_schedule.items():
                for slot in slots:
                    if slot['period'] == period_num:
                        subj = slot['subject']
                        expanded = _ABBREV_MAP.get(subj.upper(), "")
                        full_name = f" ({expanded})" if expanded else ""
                        results.append(f"{day}: Period {slot['period']} ({slot['time']}): {subj}{full_name}")
            if results:
                return "\n".join(results), search_type

        # 8. Lunch break
        if 'lunch' in q:
            search_type = "lunch_filter"
            # Find lunch break from period headers
            for h in self.period_headers:
                if 'lunch' in h.lower():
                    results.append(f"Lunch Break: {h}")
            if results:
                return "\n".join(results), search_type

        # Fallback: full context
        return self.full_context, "full"

    def _add_practical_info(self, results: List[str], subject: str):
        """Add matching practical/lab info for a subject."""
        subj_clean = re.sub(r'[^a-z]', '', subject.lower())
        for p in self.practicals:
            p_name_clean = re.sub(r'[^a-z]', '', p['name'].lower())
            if subj_clean in p_name_clean or p_name_clean in subj_clean:
                results.append(
                    f"  Lab: {p['code']} | {p['name']} | "
                    f"Staff: {p['staff_incharge']} | Asst: {p['assistant_staff']} | "
                    f"Venue: {p['venue']}"
                )

    # ─── REAL-TIME PERIOD LOOKUP ──────────────────────────────────────────────

    def _parse_time_range(self, time_str: str) -> Optional[Tuple[int, int]]:
        """Parse '1 (9.10AM TO 10.00AM)' into (start_minutes, end_minutes)."""
        match = re.search(
            r'(\d{1,2})[.:]?(\d{2})\s*(AM|PM)\s*TO\s*(\d{1,2})[.:]?(\d{2})\s*(AM|PM)',
            time_str, re.IGNORECASE
        )
        if not match:
            return None

        sh, sm, sa = int(match.group(1)), int(match.group(2)), match.group(3).upper()
        eh, em, ea = int(match.group(4)), int(match.group(5)), match.group(6).upper()

        def to_minutes(h, m, ampm):
            if ampm == 'PM' and h != 12:
                h += 12
            elif ampm == 'AM' and h == 12:
                h = 0
            return h * 60 + m

        return (to_minutes(sh, sm, sa), to_minutes(eh, em, ea))

    def _get_current_period(self) -> Optional[str]:
        """Use system clock to find what's happening RIGHT NOW."""
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        day_map = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI', 5: 'SAT'}
        today_code = day_map.get(now.weekday())

        if not today_code or today_code not in self.daily_schedule:
            return f"Today is {now.strftime('%A')}. There are no classes scheduled for today."

        today_slots = self.daily_schedule[today_code]
        current_slot = None
        next_slot = None

        for slot in today_slots:
            time_range = self._parse_time_range(slot['time'])
            if not time_range:
                continue
            start_min, end_min = time_range
            if start_min <= current_minutes < end_min:
                current_slot = slot
            elif start_min > current_minutes and next_slot is None:
                next_slot = slot
                if current_slot:
                    break

        lines = []
        lines.append(f"Current: {now.strftime('%A, %d %B %Y, %I:%M %p')}")
        lines.append(f"Today: {today_code}\n")

        if current_slot:
            subj = current_slot['subject']
            expanded = _ABBREV_MAP.get(subj.upper(), "")
            full_name = f" ({expanded})" if expanded else ""
            lines.append(f"CURRENT: Period {current_slot['period']} ({current_slot['time']}): {subj}{full_name}")
            self._add_practical_info(lines, subj)
            if next_slot:
                ns = next_slot['subject']
                ns_exp = _ABBREV_MAP.get(ns.upper(), "")
                ns_full = f" ({ns_exp})" if ns_exp else ""
                lines.append(f"\nNEXT: Period {next_slot['period']} ({next_slot['time']}): {ns}{ns_full}")
        else:
            lines.append(f"No class is currently in session at {now.strftime('%I:%M %p')}.")
            if next_slot:
                ns = next_slot['subject']
                ns_exp = _ABBREV_MAP.get(ns.upper(), "")
                ns_full = f" ({ns_exp})" if ns_exp else ""
                lines.append(f"Next: Period {next_slot['period']} ({next_slot['time']}): {ns}{ns_full}")
            else:
                lines.append("All classes for today are over.")

        lines.append(f"\n--- Full {today_code} Schedule ---")
        for slot in today_slots:
            subj = slot['subject']
            expanded = _ABBREV_MAP.get(subj.upper(), "")
            full_name = f" ({expanded})" if expanded else ""
            marker = " ← NOW" if slot == current_slot else ""
            lab_tag = " [LAB]" if slot.get("is_lab") else ""
            lines.append(f"  Period {slot['period']} ({slot['time']}): {subj}{full_name}{lab_tag}{marker}")

        return "\n".join(lines)

    def _find_subject_matches(self, q: str) -> List[str]:
        """Find schedule entries matching subject keywords."""
        results = []
        keywords = self._extract_keywords(q)
        if not keywords:
            return results

        for day, slots in self.daily_schedule.items():
            for slot in slots:
                subj_lo = slot['subject'].lower()
                # Also check against expanded names
                expanded = _ABBREV_MAP.get(slot['subject'].upper(), "").lower()
                combined = f"{subj_lo} {expanded}"
                if any(kw in combined for kw in keywords):
                    exp_str = f" ({_ABBREV_MAP.get(slot['subject'].upper(), '')})" if expanded else ""
                    results.append(
                        f"{day}: Period {slot['period']} ({slot['time']}): "
                        f"{slot['subject']}{exp_str}"
                    )

        return results

    def _extract_keywords(self, q: str) -> List[str]:
        """Extract meaningful keywords from query."""
        stop_words = {
            'what', 'is', 'the', 'for', 'in', 'on', 'at', 'a', 'an', 'and',
            'or', 'of', 'to', 'are', 'when', 'where', 'who', 'which', 'how',
            'do', 'does', 'did', 'has', 'have', 'there', 'their', 'they',
            'this', 'that', 'it', 'its', 'my', 'me', 'we', 'us', 'can',
            'will', 'would', 'should', 'could', 'may', 'shall', 'class',
            'classes', 'happening', 'schedule', 'timetable', 'tell',
            'show', 'give', 'time', 'period', 'during', 'about',
            'department', 'cse', 'staff', 'incharge', 'charge', 'assistant',
            'venue', 'lab', 'room', 'am', 'pm',
        }
        words = re.findall(r'[a-z0-9]+', q.lower())
        keywords = [w for w in words if w not in stop_words and len(w) >= 2
                     and not (w.isdigit() and len(w) <= 3)]

        # Multi-word phrase detection
        q_lo = q.lower()
        phrases = []
        if 'naan mudhalvan' in q_lo:
            phrases.append('naan mudhalvan')
        if 'operating system' in q_lo:
            phrases.extend(['os', 'operating system'])
        if 'database management' in q_lo:
            phrases.extend(['dbms', 'database management'])
        if 'devops' in q_lo:
            phrases.append('devops')
        if 'artificial intelligence' in q_lo:
            phrases.extend(['aiml', 'artificial intelligence'])
        if 'machine learning' in q_lo:
            phrases.extend(['aiml', 'machine learning'])
        if 'soft computing' in q_lo:
            phrases.extend(['soft', 'soft computing'])
        if 'cloud' in q_lo:
            phrases.append('cloud')
        if 'iot' in q_lo or 'embedded' in q_lo:
            phrases.extend(['iot', 'embedded'])
        if 'theory of computation' in q_lo:
            phrases.extend(['toc', 'theory of computation'])
        if 'algorithm' in q_lo:
            phrases.extend(['alg', 'algorithm'])
        if 'software engineering' in q_lo:
            phrases.extend(['oose', 'software engineering'])
        if 'multimedia' in q_lo:
            phrases.extend(['multi', 'multimedia'])
        if 'history' in q_lo:
            phrases.extend(['hst', 'history'])

        return keywords + phrases

    # ─── QUERY ────────────────────────────────────────────────────────────────

    def query(self, query: str, target_dept: Optional[str] = None,
              year: Optional[int] = None,
              verbose: bool = False) -> Dict[str, Any]:
        """Answer a timetable query using deterministic search + optional LLM."""
        # Switch year if requested and different from current
        if year and year != self.target_year and year in self._all_years:
            self._activate_year(year)

        if not self.daily_schedule and not self.practicals:
            return {
                "answer": "Timetable data is not available for this department.",
                "method": "timetable_pipeline",
                "search_type": "none",
            }

        # Step 1: Deterministic search
        context, search_type = self._search(query)

        if verbose:
            print(f"  [TimetableRAG] year={self.target_year}, search_type={search_type}, "
                  f"context={len(context)} chars\n")

        # Step 2: Direct bypass for filtered results (no LLM needed)
        if search_type != "full" and context.strip():
            return {
                "answer": context,
                "method": "timetable_direct_bypass",
                "search_type": search_type,
            }

        # Step 3: LLM for full context fallback
        answer = self._ask_llm(query, context)
        return {
            "answer": answer,
            "method": "timetable_pipeline",
            "search_type": search_type,
        }

    def _ask_llm(self, query: str, context: str) -> str:
        """Use LLM to generate a natural language answer from timetable context."""
        prompt = f"""You are a data extraction assistant for the {self.department} department.
Answer the question based ONLY on the data provided below.

RULES:
1. If the exact answer is in the data, extract it and answer briefly.
2. If the information is NOT explicitly stated, output: "This information is not available in the timetable."
3. NEVER use outside knowledge. NEVER guess.
4. No conversational filler – just provide the data.

DATA:
{context}

QUESTION: {query}

ANSWER:"""

        try:
            resp = requests.post(
                self.ollama.generate_endpoint,
                json={
                    "model": self.ollama.llm_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 400,
                        "num_ctx": 4096,
                    }
                },
                timeout=180
            )
            if resp.status_code == 200:
                return resp.json()['response'].strip()
            return f"Error: HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            return "Error: LLM timeout"
        except Exception as e:
            return f"Error: {str(e)}"
