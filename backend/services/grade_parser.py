import re
from utils.subject_credits import SUBJECT_CREDITS

VALID_GRADES = {"O", "A+", "A", "B+", "B", "C", "RA", "SA", "W"}
COURSE_CODE_PATTERN = re.compile(r"^[A-Z]{2,4}\d{3,4}$")

def normalize_grade(g):
    return "O" if g == "0" else g

def parse_subjects(blocks):
    words = {}
    rows = {}

    # Collect WORDs
    for b in blocks:
        if b["BlockType"] == "WORD":
            words[b["Id"]] = b["Text"]

    # Build rows
    for b in blocks:
        if b["BlockType"] == "CELL":
            r = b["RowIndex"]
            text = ""

            if "Relationships" in b:
                for rel in b["Relationships"]:
                    if rel["Type"] == "CHILD":
                        for cid in rel["Ids"]:
                            text += words.get(cid, "") + " "

            rows.setdefault(r, []).append(text.strip())

    subjects = []

    for r in sorted(rows):
        subject_code = None
        grade = None

        for cell in rows[r]:
            cell = cell.strip()

            # ✅ Subject code detection (generic)
            if COURSE_CODE_PATTERN.match(cell) and cell in SUBJECT_CREDITS:
                subject_code = cell

            # ✅ Grade detection
            elif cell in VALID_GRADES or cell == "0":
                grade = normalize_grade(cell)

        if subject_code and grade:
            subjects.append({
                "subject_code": subject_code,
                "credits": SUBJECT_CREDITS[subject_code],
                "grade": grade
            })

    return subjects
