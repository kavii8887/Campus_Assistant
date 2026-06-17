import sys
import subprocess
env_python = r"d:\projects\eduQ\backend\venv\Scripts\python.exe"
subprocess.run([env_python, "-m", "pip", "install", "pylint"], check=True)
res = subprocess.run([env_python, "-m", "pylint", "backend/timetable_pipeline.py", "backend/department_router.py"], capture_output=True, text=True)
with open("pylint_out.txt", "w", encoding="utf-8") as f:
    f.write(res.stdout)
    f.write(res.stderr)
