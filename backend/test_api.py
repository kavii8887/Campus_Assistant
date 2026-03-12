import requests
import time
import json

URL = "http://localhost:8000/api/query"

queries = [
    {"name": "Syllabus", "msg": "tell me about unit 1 for CCS342", "dept": "CSE"},
    {"name": "Subject Code", "msg": "what is the subject code for devops", "dept": "CSE"},
    {"name": "Credits", "msg": "how many credits is operating systems", "dept": "CSE"},
    {"name": "Staff", "msg": "who is the HOD of computer science", "dept": "CSE"},
    {"name": "Timetable", "msg": "schedule for monday", "dept": "CSE"}
]

print("=== STARTING RAG PIPELINE TESTS ===")

for q in queries:
    print(f"\nTesting Pipeline: {q['name']}")
    print(f"Query: '{q['msg']}'")
    
    payload = {
        "message": q["msg"],
        "session_id": "test_script_session_1",
        "department": q["dept"]
    }
    
    start = time.time()
    try:
        response = requests.post(URL, json=payload, timeout=200)
        dur = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            print(f"Success ({dur:.2f}s)".encode('ascii', 'ignore').decode())
            print(f"Method: {data.get('method')}")
            print(f"LLM Used: {data.get('llm_used')}")
            # encode to handle emoji/special char encoding errors in windows terminal
            ans_snippet = (data.get('answer', '')[:200] + '...').replace('\n', ' ')
            print(f"Answer Preview: {ans_snippet.encode('ascii','ignore').decode()}")
            if data.get('method') == 'error':
                print(f"DETECTED LOGICAL ERROR IN RESPONSE: {data.get('answer', '').encode('ascii','ignore').decode()}")
        else:
            print(f"HTTP Error {response.status_code}")
    except Exception as e:
        print(f"Request failed: {e}")

print("\n=== TESTS COMPLETE ===")
