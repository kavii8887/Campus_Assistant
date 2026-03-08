"""
attendance_handlers.py — Deterministic Attendance Logic
========================================================
CRITICAL RULES:
- NO LLM reasoning
- ALL calculations use pandas on raw Excel
- Deterministic status logic per regulation
- Department-scoped via session metadata

Version: 1.0
"""

import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Tuple
import numpy as np

# ── Attendance Status Rules (Regulation) ──────────────────────────────────────

def get_attendance_status(percentage: float) -> str:
    """
    Deterministic status per regulation.
    
    Rules:
        >= 75%: Eligible for exams
        65-74%: Condonation possible
        < 65%: Not eligible – must repeat semester
    """
    if percentage >= 75:
        return "Eligible for exams"
    elif percentage >= 65:
        return "Condonation possible"
    else:
        return "Not eligible – must repeat semester"


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_attendance_dataframe(
    dept: str,
    year: int,
    semester: str,
    persist_path: str = "./vector_db"
) -> Optional[pd.DataFrame]:
    """
    Load latest raw attendance Excel file.
    
    Args:
        dept: Department code (CSE, ECE, etc.)
        year: Student year (1-4)
        semester: 'odd' or 'even'
        persist_path: Base path to vector_db
    
    Returns:
        DataFrame or None if not found
    """
    raw_dir = Path(persist_path) / dept / "attendance" / "raw"
    
    if not raw_dir.exists():
        return None
    
    # Find Excel files matching year/semester pattern
    excel_files = list(raw_dir.glob(f"*_year{year}_{semester}*.xlsx"))
    
    if not excel_files:
        # Try without specific pattern
        excel_files = list(raw_dir.glob("*.xlsx"))
    
    if not excel_files:
        return None
    
    # Use latest file (by modification time)

    latest_file = max(excel_files, key=lambda p: p.stat().st_mtime)
    print("\n[DEBUG] Loading attendance file:", latest_file)

    
    try:
        df = pd.read_excel(latest_file)
        return df
    except Exception as e:
        print(f"Error loading {latest_file}: {e}")
        return None


# ── Calculation Functions ─────────────────────────────────────────────────────

def calculate_subject_percentages(
    df: pd.DataFrame,
    register_no: str
) -> Dict[str, float]:
    """
    Calculate attendance percentage per subject.
    
    Expected Excel format:
        - Column 'Register_No' or 'RegisterNo' or 'Reg_No'
        - Subject columns with attended/total format or separate columns
    
    Returns:
        Dict[subject_code, percentage]
    """
    # Normalize register number
    register_no = str(register_no).strip().upper()
    
    # Find register number column
    reg_col = None
    print("\n[DEBUG] All columns detected:")
    print(df.columns.tolist())

    for col in df.columns:
        col_lower = str(col).lower().replace('_', '').replace(' ', '')
        if col_lower in ['registerno', 'regno', 'registernum']:
            reg_col = col
            break
    print("\n[DEBUG] Detected register column:", reg_col)
    print("[DEBUG] Session register_no:", register_no)
    print("[DEBUG] Raw register column dtype:", df[reg_col].dtype)

# Show first few raw values exactly as pandas sees them
    print("[DEBUG] First 10 register values (raw):")
    print(df[reg_col].head(10).tolist())

# Show normalized values that your filter uses
    normalized_series = df[reg_col].astype(str).str.strip().str.upper()
    print("[DEBUG] First 10 normalized register values:")
    print(normalized_series.head(10).tolist())

    if reg_col is None:
        return {}
    
    # Find student row
    normalized_series = df[reg_col].astype(str).str.strip().str.upper()

    print("[DEBUG] Comparing against:", register_no)
    print("[DEBUG] Exact matches found:", (normalized_series == register_no).sum())

    student_row = df[normalized_series == register_no]

    
    if student_row.empty:
        return {}
    
    student_row = student_row.iloc[0]
    
    # Extract subject percentages
    subject_percentages = {}
    
    for col in df.columns:
        col_str = str(col).upper()
        
        # Skip non-subject columns
        if any(skip in col_str for skip in ['REGISTER', 'NAME', 'ROLL', 'OVERALL', 'TOTAL']):
            continue
        
        # Try to extract percentage
        value = student_row[col]
        
        if pd.isna(value):
            continue
        
        # Handle different formats
        if isinstance(value, str):
            # Format: "45/60" or "75%"
            if '/' in value:
                parts = value.split('/')
                if len(parts) == 2:
                    try:
                        attended = float(parts[0].strip())
                        total = float(parts[1].strip())
                        if total > 0:
                            percentage = (attended / total) * 100
                            subject_percentages[col] = round(percentage, 2)
                    except:
                        pass
            elif '%' in value:
                try:
                    percentage = float(value.replace('%', '').strip())
                    subject_percentages[col] = round(percentage, 2)
                except:
                    pass
        elif isinstance(value, (int, float, np.integer, np.floating)):

    # Treat numeric values as attended count out of 31 (demo default)
            total_classes = 31
            percentage = (float(value) / total_classes) * 100
            subject_percentages[col] = round(percentage, 2)

    
    return subject_percentages


def calculate_overall_percentage(
    df: pd.DataFrame,
    register_no: str
) -> Optional[float]:
    """
    Calculate overall attendance percentage across all subjects.
    
    Returns:
        Overall percentage or None
    """
    subject_percentages = calculate_subject_percentages(df, register_no)
    
    if not subject_percentages:
        return None
    
    # Average across all subjects
    overall = sum(subject_percentages.values()) / len(subject_percentages)
    return round(overall, 2)


# ── Query Handlers ────────────────────────────────────────────────────────────

def handle_attendance_percentage(
    session,
    router,
    persist_path: str = "./vector_db"
) -> str:
    """
    Handle "what is my attendance percentage" queries.
    
    Returns formatted response with subject-wise and overall percentages.
    """
    # Extract session metadata
    register_no = getattr(session, 'register_no', None)
    department = getattr(session, 'student_department', None)
    year = getattr(session, 'student_year', None)
    semester = getattr(session, 'student_semester', None)
    
    # Validate metadata
    if not all([register_no, department, year, semester]):
        return "Attendance information requires student details (register number, department, year, semester). Please contact administrator."
    
    # Load data
    df = load_attendance_dataframe(department, year, semester, persist_path)
    
    if df is None:
        return f"No attendance data found for {department} Year {year} {semester.upper()} semester."
    
    # Calculate percentages
    subject_percentages = calculate_subject_percentages(df, register_no)
    
    if not subject_percentages:
        return f"No attendance records found for Register No: {register_no}"
    
    overall = calculate_overall_percentage(df, register_no)
    status = get_attendance_status(overall) if overall else "Unknown"
    
    # Format response
    lines = ["Attendance Percentage:\n"]
    lines.append("Subject-wise:")
    
    for subject, percentage in sorted(subject_percentages.items()):
        lines.append(f"  {subject}: {percentage}%")
    
    lines.append(f"\nOverall Attendance: {overall}%")
    lines.append(f"Status: {status}")
    
    return "\n".join(lines)


def handle_attendance_status(
    session,
    router,
    persist_path: str = "./vector_db"
) -> str:
    """
    Handle "am I eligible for exams" / "attendance status" queries.
    
    Returns eligibility status based on regulations.
    """
    # Extract session metadata
    register_no = getattr(session, 'register_no', None)
    department = getattr(session, 'student_department', None)
    year = getattr(session, 'student_year', None)
    semester = getattr(session, 'student_semester', None)
    
    if not all([register_no, department, year, semester]):
        return "Attendance status requires student details. Please contact administrator."
    
    # Load data
    df = load_attendance_dataframe(department, year, semester, persist_path)
    
    if df is None:
        return f"No attendance data available for {department} Year {year} {semester.upper()} semester."
    
    # Calculate overall percentage
    overall = calculate_overall_percentage(df, register_no)
    
    if overall is None:
        return f"No attendance records found for Register No: {register_no}"
    
    # Get status
    status = get_attendance_status(overall)
    
    # Format response
    return f"Attendance Status: {overall}%\n{status}"


def handle_attended_classes(
    session,
    router,
    persist_path: str = "./vector_db"
) -> str:
    """
    Handle "how many classes did I attend" queries.
    
    Returns class counts per subject.
    """
    # Extract session metadata
    register_no = getattr(session, 'register_no', None)
    department = getattr(session, 'student_department', None)
    year = getattr(session, 'student_year', None)
    semester = getattr(session, 'student_semester', None)
    
    if not all([register_no, department, year, semester]):
        return "Class attendance information requires student details. Please contact administrator."
    
    # Load data
    df = load_attendance_dataframe(department, year, semester, persist_path)
    
    if df is None:
        return f"No attendance data found for {department} Year {year} {semester.upper()} semester."
    
    # Find register number column
    register_no = str(register_no).strip().upper()
    reg_col = None
    for col in df.columns:
        col_lower = str(col).lower().replace('_', '').replace(' ', '')
        if col_lower in ['registerno', 'regno', 'registernum']:
            reg_col = col
            break
    
    if reg_col is None:
        return "Unable to find register number column in attendance data."
    
    # Find student row
    student_row = df[df[reg_col].astype(str).str.strip().str.upper() == register_no]
    
    if student_row.empty:
        return f"No attendance records found for Register No: {register_no}"
    
    student_row = student_row.iloc[0]
    
    # Extract class counts
    lines = ["Classes Attended:\n"]
    total_attended = 0
    total_classes = 0
    
    for col in df.columns:
        col_str = str(col).upper()
        
        # Skip non-subject columns
        if any(skip in col_str for skip in ['REGISTER', 'NAME', 'ROLL', 'OVERALL', 'TOTAL']):
            continue
        
        value = student_row[col]
        
        if pd.isna(value):
            continue
        
        # Parse "attended/total" format
        if isinstance(value, str) and '/' in value:
            parts = value.split('/')
            if len(parts) == 2:
                try:
                    attended = int(float(parts[0].strip()))
                    total = int(float(parts[1].strip()))
                    lines.append(f"  {col}: {attended}/{total}")
                    total_attended += attended
                    total_classes += total
                except:
                    pass
    
    if total_classes > 0:
        lines.append(f"\nTotal: {total_attended}/{total_classes} classes")
    
    return "\n".join(lines)


# ── Dispatcher ────────────────────────────────────────────────────────────────

def dispatch(
    query_type: str,
    session,
    router,
    persist_path: str = "./vector_db"
) -> str:
    """
    Dispatch attendance query to appropriate handler.
    
    Args:
        query_type: One of QT_ATTENDANCE_PERCENTAGE, QT_ATTENDANCE_STATUS, QT_ATTENDANCE_COUNT
        session: SessionState with student metadata
        router: DepartmentRouter instance
        persist_path: Path to vector_db
    
    Returns:
        Formatted answer string
    """
    from routing import (
        QT_ATTENDANCE_PERCENTAGE,
        QT_ATTENDANCE_STATUS,
        QT_ATTENDANCE_COUNT
    )
    
    if query_type == QT_ATTENDANCE_PERCENTAGE:
        return handle_attendance_percentage(session, router, persist_path)
    
    elif query_type == QT_ATTENDANCE_STATUS:
        return handle_attendance_status(session, router, persist_path)
    
    elif query_type == QT_ATTENDANCE_COUNT:
        return handle_attended_classes(session, router, persist_path)
    
    return "Unknown attendance query type."