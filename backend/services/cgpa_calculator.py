from utils.constants import GRADE_POINTS, EXCLUDED_GRADES
from utils.validator import is_valid_subject

def calculate_cgpa(subjects):
    total_points = 0
    total_credits = 0

    for s in subjects:

        # ✅ NEW: validation check
        if not is_valid_subject(s):
            continue

        grade = s["grade"]
        credits = s["credits"]

        if grade in EXCLUDED_GRADES:
            continue

        total_points += credits * GRADE_POINTS[grade]
        total_credits += credits

    if total_credits == 0:
        return 0.0, 0.0

    cgpa = round(total_points / total_credits, 2)
    percentage = round(cgpa * 10, 2)

    return cgpa, percentage
