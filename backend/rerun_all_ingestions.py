import os
import re
import subprocess
from pathlib import Path

def rerun_all():
    base_dir = Path(__file__).parent.resolve()
    python_exe = base_dir / "venv" / "Scripts" / "python.exe"
    
    # Set PYTHONPATH and PYTHONIOENCODING
    env = os.environ.copy()
    env["PYTHONPATH"] = str(base_dir)
    env["PYTHONIOENCODING"] = "utf-8"
    
    print("=== Rerunning Syllabus Ingestion ===")
    ece_md = base_dir / "data" / "ECE" / "ECE.md"
    if ece_md.exists():
        cmd = [str(python_exe), "ingest/ingest_syllabus.py", str(ece_md), "--dept", "ECE"]
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=str(base_dir), env=env)
    else:
        print(f"File not found: {ece_md}")

    print("\n=== Rerunning Attendance Ingestion ===")
    vector_db_dir = base_dir / "vector_db"
    if vector_db_dir.exists():
        for dept_dir in vector_db_dir.iterdir():
            if dept_dir.is_dir() and dept_dir.name not in ["global"]:
                raw_dir = dept_dir / "attendance" / "raw"
                if raw_dir.exists():
                    for xlsx_file in raw_dir.glob("*.xlsx"):
                        match = re.search(r'_year(\d+)_([^_]+)_(\d{4}-\d{2}-\d{2})\.xlsx$', xlsx_file.name)
                        if match:
                            year = match.group(1)
                            semester = match.group(2)
                            date = match.group(3)
                            
                            # Handle semester issues for CLI compatibility
                            if semester.lower() not in ['odd', 'even']:
                                print(f"Warning: semester '{semester}' is not valid for CLI. Using 'odd'.")
                                semester = 'odd'
                                
                            dept = dept_dir.name
                            print(f"\nIngesting attendance for {dept}: {xlsx_file.name}")
                            cmd = [
                                str(python_exe), "ingest/ingest_attendance.py", 
                                str(xlsx_file), "--dept", dept, "--year", year, 
                                "--semester", semester, "--date", date
                            ]
                            print(f"Running: {' '.join(cmd)}")
                            subprocess.run(cmd, cwd=str(base_dir), env=env)

    stray_ece_xlsx = base_dir / "data" / "ECE" / "ece.xlsx"
    if stray_ece_xlsx.exists():
        print(f"\nFound stray file: {stray_ece_xlsx}. Ingesting as ECE, Year 2, odd semester (default)")
        cmd = [
            str(python_exe), "ingest/ingest_attendance.py", 
            str(stray_ece_xlsx), "--dept", "ECE", "--year", "2", 
            "--semester", "odd", "--date", "2024-01-01"
        ]
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=str(base_dir), env=env)

if __name__ == "__main__":
    rerun_all()
