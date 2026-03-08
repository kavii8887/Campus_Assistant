# =========================================================
# 🔥 FULL DROP-IN FASTAPI SERVER (FINAL STABLE BUILD)
# =========================================================

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
import shutil
import uuid

from runtime_engine import AcademicRAGSystem
from ingest.ingest_attendance import AttendanceIngestionPipeline

# ⭐ OCR SERVICES
from services.textract_service import extract_tables
from services.grade_parser import parse_subjects
from services.cgpa_calculator import calculate_cgpa
from utils.image_utils import preprocess_image


# =========================================================
# APP INIT
# =========================================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag = AcademicRAGSystem(enable_sessions=True)

# =========================================================
# ⭐ DEPARTMENT NORMALIZER
# =========================================================
def normalize_department(dept: str | None) -> str | None:
    if not dept:
        return None

    d = dept.strip().upper()

    mapping = {
        "BE COMPUTER SCIENCE AND ENGINEERING": "CSE",
        "COMPUTER SCIENCE AND ENGINEERING": "CSE",
        "CSE": "CSE",
        "BE MECHANICAL ENGINEERING": "MECH",
        "MECHANICAL ENGINEERING": "MECH",
        "MECH": "MECH",
        "BE ELECTRICAL COMMUNICATION ENGINEERING": "ECE",
        "ELECTRICAL COMMUNICATION ENGINEERING": "ECE",
        "ECE": "ECE",
        "BE ELECTRICAL AND ELECTRONICS ENGINEERING": "EEE",
        "ELECTRICAL AND ELECTRONICS ENGINEERING": "EEE",
        "EEE": "EEE",
        "BE CIVIL ENGINEERING": "CIVIL",
        "CIVIL ENGINEERING": "CIVIL",
        "CIVIL": "CIVIL",
        "BE INFORMATION TECHNOLOGY": "CSE",
        "INFORMATION TECHNOLOGY": "CSE",
        "IT": "CSE",
    }

    return mapping.get(d, d)


# =========================================================
# REQUEST MODEL
# =========================================================
class QueryRequest(BaseModel):
    message: str
    session_id: str
    register_no: str | None = None
    department: str | None = None
    year: int | None = None
    semester: str | None = None


# =========================================================
# 🔥 RAG QUERY ENDPOINT (BUG FIX: Session management)
# =========================================================
@app.post("/api/query")
def query(req: QueryRequest):
    
    # BUG FIX: Properly handle session creation
    if rag.session_manager:
        existing = rag.session_manager.peek_session(req.session_id)
        if not existing:
            # Create a new session with the REQUESTED session_id
            from session_manager import SessionState
            import time
            
            new_session = SessionState(
                session_id=req.session_id,
                last_activity=time.time(),
                register_no=req.register_no,
                student_year=req.year,
                student_semester=req.semester.lower() if req.semester else None,
                student_department=normalize_department(req.department)
            )
            rag.session_manager.sessions[req.session_id] = new_session

    # Set department if provided
    normalized_dept = normalize_department(req.department)
    if normalized_dept:
        rag.set_department(normalized_dept, session_id=req.session_id)

    # Update session metadata
    if rag.session_manager:
        rag.session_manager.update_session(
            req.session_id,
            register_no=req.register_no,
            student_year=req.year,
            student_semester=req.semester,
            student_department=normalized_dept,
        )

    # Execute query
    result = rag.query(
        req.message,
        session_id=req.session_id,
        verbose=False
    )

    return result


# =========================================================
# 🔥 OCR RESULT ANALYSIS
# =========================================================
@app.post("/api/analyze-result")
async def analyze_result(file: UploadFile = File(...)):

    image_bytes = await file.read()
    image_bytes = preprocess_image(image_bytes)

    blocks = extract_tables(image_bytes)

    subjects = parse_subjects(blocks)
    cgpa, percentage = calculate_cgpa(subjects)

    return {
        "subjects": subjects,
        "gpa": cgpa,
        "percentage": percentage
    }


# =========================================================
# 🔥 ADMIN ATTENDANCE UPLOAD ROUTE
# =========================================================
@app.post("/api/attendance/upload")
async def upload_attendance(
    file: UploadFile = File(...),
    dept: str = Form(...),
    year: int = Form(...),
    semester: str = Form(...),
    date: str = Form(...),
):

    if not file.filename.endswith(".xlsx"):
        return {"ok": False, "error": "Only .xlsx files allowed"}

    upload_dir = Path("temp_uploads")
    upload_dir.mkdir(exist_ok=True)

    temp_path = upload_dir / f"{uuid.uuid4()}_{file.filename}"

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        normalized = normalize_department(dept)

        pipeline = AttendanceIngestionPipeline(
            department=normalized
        )

        pipeline.ingest(
            excel_path=str(temp_path),
            year=year,
            semester=semester.lower(),
            date=date
        )

    except Exception as e:
        return {"ok": False, "error": str(e)}

    finally:
        if temp_path.exists():
            temp_path.unlink()

    return {
        "ok": True,
        "message": "Attendance uploaded and ingested successfully",
        "department": normalized,
        "year": year,
        "semester": semester.lower(),
        "date": date
    }