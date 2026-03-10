import sys
import os

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from staff_pipeline import StaffPipeline

# Dummy Ollama client for testing
class DummyOllama:
    def generate(self, prompt, **kwargs):
        return "LLM Fallback"
    def embed_single(self, text):
        return []

def run_tests():
    pipeline = StaffPipeline(DummyOllama(), json_path="data/staffs.json")
    
    questions = [
        # 1. Direct hit with name
        "give email id of archana mam", # Not in DB, should fallback or say what it knows
        "give phone number of devi mam", # Not in DB, should fallback
        "What is the email of Dr. A. M. Kalpana?", # In CSE, should get direct email
        "What is the phone number of Dr. C. Priya?", # In ECE, should get direct phone
        
        # 2. General department queries
        "Who is the HOD of CSE?", # Should use LLM, since it doesn't match direct email/phone
        "List all staff in Civil Engineering", # Should use LLM
        "Does anyone specialize in Machine Learning?", # Direct answer YES
        
        # 3. Principal specific queries
        "What is the email of the principal?", # Should get direct
        "Who is the vice principal?", # Should use LLM
        
        # 4. Non-existent person
        "What is the email of Dr. Suresh Kumar?", # Might fallback if score not high
    ]

    for i, q in enumerate(questions, 1):
        print(f"\n--- Test {i} ---")
        print(f"Q: {q}")
        res = pipeline.query(q)
        print(f"A: {res['answer']}")
        print(f"Method: {res['method']}")

if __name__ == "__main__":
    run_tests()
