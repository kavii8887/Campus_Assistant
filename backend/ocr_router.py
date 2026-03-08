from fastapi import APIRouter, File, UploadFile
from services.textract_service import extract_tables
from services.grade_parser import parse_subjects
from services.cgpa_calculator import calculate_cgpa
from utils.image_utils import preprocess_image

router = APIRouter()

@router.post("/analyze-result")
async def analyze_result(file: UploadFile = File(...)):
    image_bytes = await file.read()
    image_bytes = preprocess_image(image_bytes)

    blocks = extract_tables(image_bytes)

    # DEBUG TABLE EXTRACTION
    words = {}
    rows = {}

    for b in blocks:
        if b["BlockType"] == "WORD":
            words[b["Id"]] = b["Text"]

    for b in blocks:
        if b["BlockType"] == "CELL":
            r = b["RowIndex"]
            c = b["ColumnIndex"]
            text = ""

            if "Relationships" in b:
                for rel in b["Relationships"]:
                    if rel["Type"] == "CHILD":
                        for cid in rel["Ids"]:
                            text += words.get(cid, "") + " "

            rows.setdefault(r, {})[c] = text.strip()

    print("\n🔍 RAW TABLE ROWS FROM FASTAPI:")
    for r in sorted(rows):
        print(f"Row {r}: {rows[r]}")

    subjects = parse_subjects(blocks)
    print("PARSED SUBJECTS:", subjects)

    cgpa, percentage = calculate_cgpa(subjects)

    return {
        "subjects": subjects,
        "cgpa": cgpa,
        "percentage": percentage
    }
