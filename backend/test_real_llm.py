import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from staff_pipeline import StaffPipeline
from ollama_client import OllamaClient

def run_tests():
    client = OllamaClient()
    pipeline = StaffPipeline(client, json_path="data/staffs.json")
    
    questions = [
        "give email id of archana mam",
        "give phone number of devi mam",
        "What is the email of Dr. A. M. Kalpana?",
        "What is the phone number of Dr. C. Priya?",
        "Who is the HOD of CSE?",
        "List all staff in Civil Engineering",
        "Does anyone specialize in Machine Learning?",
        "What is the email of the principal?",
        "Who is the vice principal?",
        "What is the email of Dr. Suresh Kumar?",
    ]

    for i, q in enumerate(questions, 1):
        print(f"\n--- Test {i} ---")
        print(f"Q: {q}")
        res = pipeline.query(q)
        print(f"A: {res['answer']}")
        print(f"Method: {res['method']}")

if __name__ == "__main__":
    run_tests()
