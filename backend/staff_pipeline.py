"""
staff_pipeline.py — Staff RAG Pipeline (V5 — Hybrid: Python Filter + LLM)
===========================================================================
Since the staff directory is small (~30 records), we load ALL data in memory.

For each query:
  1. Python keyword filter narrows down relevant records (fast, deterministic)
  2. If filter finds matches → send ONLY those to LLM for natural language answer
  3. If filter finds nothing → send ALL data to LLM as fallback

This hybrid approach ensures:
  ✓ Zero missing data (fallback always sends everything)
  ✓ Fast responses (small filtered context)
  ✓ Accurate answers (LLM gets focused context)
"""

import json
import re
from typing import Dict, Any, List, Optional
from pathlib import Path


class StaffPipeline:

    def __init__(self, ollama_client, json_path: str = "data/staffs.json"):
        self.ollama = ollama_client
        self.json_path = json_path
        self.records: List[Dict[str, Any]] = []
        self.record_lines: List[str] = []       # one-line text per record
        self.full_context: str = ""

        self._ingest()

    # ─── INGEST ──────────────────────────────────────────────────────────────

    def _ingest(self):
        """Load staffs.json, build records and text lines."""
        path = Path(self.json_path)
        if not path.exists():
            print(f"⚠ Staff data not found at {self.json_path}")
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        dept_map = {
            "Computer Science Engineering": "CSE",
            "Civil Engineering": "CIVIL",
            "Electrical and Electronics Engineering": "EEE",
            "Electronics and Communication Engineering": "ECE",
            "Mechanical Engineering": "MECH",
            "Information Technology": "IT",
            "Chemistry": "CHEMISTRY",
            "English": "ENGLISH",
            "Physics": "PHYSICS",
            "Tamil": "TAMIL",
            "Mathematics": "MATHEMATICS",
        }

        # ── Institution
        inst = data.get("institution", {})
        if inst:
            addr = inst.get("address", {})
            contact = inst.get("contact", {})
            rec = {
                "type": "institution",
                "name": inst.get("name", ""),
                "short_name": inst.get("short_name", ""),
                "department": "GLOBAL",
                "designation": "Institution",
            }
            line = (
                f"INSTITUTION: {rec['name']} ({rec['short_name']})"
                f" | Address: {addr.get('line','')}, {addr.get('district','')}, "
                f"{addr.get('state','')} {addr.get('pincode','')}"
                f" | Landline: {contact.get('landline','')}"
            )
            self.records.append(rec)
            self.record_lines.append(line)

        # ── Administration - Principal
        admin = data.get("administration", {})
        principal = admin.get("principal", {})
        if principal:
            pa = principal.get("personal_assistant", {})
            rec = {
                "type": "admin",
                "name": principal.get("name", ""),
                "designation": principal.get("designation", "Principal"),
                "department": "GLOBAL",
                "qualification": principal.get("qualification", ""),
                "specialization": principal.get("specialization", ""),
                "email": principal.get("contact", {}).get("official_email", ""),
                "phone": ", ".join(principal.get("contact", {}).get("mobile_numbers", [])),
            }
            line = (
                f"ADMIN: {rec['name']} | Designation: {rec['designation']}"
                f" | Qualification: {rec['qualification']}"
                f" | Specialization: {rec['specialization']}"
                f" | Research: {', '.join(principal.get('research_interests', []))}"
                f" | Experience: {principal.get('total_experience_years', '')} years"
                f" | Email: {rec['email']}"
                f" | Phone: {rec['phone']}"
                f" | PA: {pa.get('name', '')} (Phone: {pa.get('contact_number', '')})"
            )
            self.records.append(rec)
            self.record_lines.append(line)

        # ── Administration - Hierarchy
        for person in admin.get("administrative_hierarchy", []):
            rec = {
                "type": "admin",
                "name": person.get("name", ""),
                "designation": person.get("designation", ""),
                "department": "GLOBAL",
                "qualification": "",
                "specialization": "",
                "email": "",
                "phone": "",
            }
            line = f"ADMIN: {rec['name']} | Designation: {rec['designation']}"
            self.records.append(rec)
            self.record_lines.append(line)

        # ── Department staff
        for dept_obj in data.get("departments", []):
            full_name = dept_obj.get("department", "Unknown")
            acronym = dept_map.get(full_name, full_name.upper())

            for staff in dept_obj.get("staff", []):
                rec = {
                    "type": "staff",
                    "name": staff.get("name", ""),
                    "designation": staff.get("designation", ""),
                    "department": acronym,
                    "department_full": full_name,
                    "qualification": staff.get("qualification", ""),
                    "specialization": staff.get("area_of_specialization", ""),
                    "email": staff.get("email", ""),
                    "phone": staff.get("contact_number", ""),
                    "experience": staff.get("teaching_experience_years", ""),
                }
                parts = [
                    f"STAFF: {rec['name']}",
                    f"Department: {full_name} ({acronym})",
                    f"Designation: {rec['designation']}",
                ]
                if rec["qualification"]:
                    parts.append(f"Qualification: {rec['qualification']}")
                if rec["specialization"]:
                    parts.append(f"Specialization: {rec['specialization']}")
                if rec["email"]:
                    parts.append(f"Email: {rec['email']}")
                if rec["phone"]:
                    parts.append(f"Phone: {rec['phone']}")
                if rec.get("experience"):
                    parts.append(f"Experience: {rec['experience']} years")
                self.records.append(rec)
                self.record_lines.append(" | ".join(parts))

        self.full_context = "\n".join(self.record_lines)
        print(f"✓ Staff Pipeline: Loaded {len(self.records)} records ({len(self.full_context)} chars)")

    # ─── PYTHON KEYWORD FILTER ───────────────────────────────────────────────

    def _filter_records(self, query: str) -> List[int]:
        """
        Fast Python keyword filter. Returns indices of matching records.
        We extract meaningful keywords from the query and match against
        record fields.
        """
        q = query.lower()
        q_clean = re.sub(r'[^a-z0-9\s]', '', q)
        words = [w for w in q_clean.split() if len(w) > 2]

        # Department detection
        dept_keywords = {
            "cse": "CSE", "computer": "CSE", "computer science": "CSE",
            "civil": "CIVIL",
            "eee": "EEE", "electrical": "EEE",
            "ece": "ECE", "electronics": "ECE",
            "mech": "MECH", "mechanical": "MECH",
            "it": "IT", "information technology": "IT",
            "chemistry": "CHEMISTRY", "physics": "PHYSICS",
            "english": "ENGLISH", "tamil": "TAMIL",
            "mathematics": "MATHEMATICS", "maths": "MATHEMATICS",
        }
        target_dept = None
        for kw, code in dept_keywords.items():
            if kw in q:
                target_dept = code
                break

        # Role detection
        role_keywords = {
            "principal": "principal",
            "vice principal": "vice principal",
            "hod": "head of the department",
            "head of department": "head of the department",
            "bursar": "bursar",
            "superintendent": "superintendent",
        }
        target_role = None
        for kw, role in role_keywords.items():
            if kw in q:
                target_role = role
                # Handle "vice principal" vs "principal"
                if kw == "principal" and "vice" in q:
                    target_role = "vice principal"
                break

        matches = []
        for i, rec in enumerate(self.records):
            score = 0
            rec_text = self.record_lines[i].lower()
            name_lower = rec.get("name", "").lower()
            desig_lower = rec.get("designation", "").lower()
            dept = rec.get("department", "")
            spec_lower = rec.get("specialization", "").lower()

            # Name match (highest priority)
            name_parts = re.sub(r'[^a-z\s]', '', name_lower).split()
            for part in name_parts:
                if len(part) > 2 and part in q:
                    score += 50

            # Department match
            if target_dept and dept == target_dept:
                score += 30

            # Role match
            if target_role:
                if target_role == "vice principal" and "vice" in desig_lower and "principal" in desig_lower:
                    score += 40
                elif target_role == "principal" and "vice" not in q and "principal" in desig_lower:
                    score += 40
                elif target_role in desig_lower:
                    score += 40

            # Specialization match
            for word in words:
                if word in spec_lower:
                    score += 35

            # General keyword match against full record text
            for word in words:
                if word in rec_text and word not in {'the', 'who', 'what', 'how', 'does', 'anyone',
                    'list', 'all', 'give', 'show', 'staff', 'department', 'many', 'years', 
                    'email', 'mail', 'phone', 'contact', 'number'}:
                    score += 5

            if score > 10:
                matches.append((i, score))

        matches.sort(key=lambda x: -x[1])
        return [i for i, _ in matches]

    # ─── DIRECT PYTHON ANSWERS (bypass LLM for simple factual queries) ────────

    def _try_direct_answer(self, query: str, matched_indices: List[int]) -> Optional[str]:
        """
        For simple factual queries, answer directly from records without LLM.
        Returns None if this query needs LLM reasoning.
        """
        if not matched_indices:
            return None

        q = query.lower()

        # "Does anyone specialize in X?" → search specialization fields
        if any(kw in q for kw in ["specialize", "specialization", "specializ", "expert", "research area"]):
            results = []
            for i in matched_indices:
                rec = self.records[i]
                spec = rec.get("specialization", "")
                if spec:
                    # Check if query keywords match specialization
                    q_words = [w for w in re.sub(r'[^a-z\s]', '', q).split() if len(w) > 3]
                    spec_lower = spec.lower()
                    if any(w in spec_lower for w in q_words):
                        dept_info = f" ({rec.get('department', '')})" if rec.get("department") else ""
                        results.append(f"**{rec['name']}**{dept_info} — Specialization: {spec}")
            if results:
                return "Yes! " + "\n".join(results)

        # "What is the email of X?"
        if any(kw in q for kw in ["email", "mail id", "email address", "mail address"]):
            rec = self.records[matched_indices[0]]
            name_lower = rec.get("name", "").lower()
            name_parts = [p for p in re.sub(r'[^a-z\s]', '', name_lower).split() if len(p) > 2]
            role_lower = rec.get("designation", "").lower()
            
            mentions_name = any(p in q for p in name_parts)
            mentions_role = any(r in q for r in ["principal", "hod", "head", "director"]) and any(r in role_lower for r in ["principal", "head", "director"])
            
            if mentions_name or mentions_role:
                email = rec.get("email", "")
                if email:
                    return f"The email of **{rec['name']}** is **{email}**"
                return f"That information is not available in the staff directory for {rec.get('name', 'this person')}."

        # "What is the phone/contact of X?"
        if any(kw in q for kw in ["phone", "contact number", "mobile", "call"]):
            rec = self.records[matched_indices[0]]
            name_lower = rec.get("name", "").lower()
            name_parts = [p for p in re.sub(r'[^a-z\s]', '', name_lower).split() if len(p) > 2]
            role_lower = rec.get("designation", "").lower()
            
            mentions_name = any(p in q for p in name_parts)
            mentions_role = any(r in q for r in ["principal", "hod", "head", "director"]) and any(r in role_lower for r in ["principal", "head", "director"])
            
            if mentions_name or mentions_role:
                phone = rec.get("phone", "")
                if phone:
                    return f"The phone number of **{rec['name']}** is **{phone}**"
                return f"That information is not available in the staff directory for {rec.get('name', 'this person')}."

        return None

    # ─── QUERY ───────────────────────────────────────────────────────────────

    def query(self, query_text: str, current_dept: str = None) -> Dict[str, Any]:
        """
        1. Python filter narrows records
        2. Try direct Python answer (no LLM needed for simple facts)
        3. LLM answers from filtered context
        4. If no filter matches, send ALL data as fallback
        """
        if not self.records:
            return self._result(query_text, "Staff directory is not loaded.", "error")

        # Step 1: Filter
        matched_indices = self._filter_records(query_text)

        # Step 2: Try direct answer (bypass LLM for simple facts)
        direct = self._try_direct_answer(query_text, matched_indices)
        if direct:
            print(f"  [StaffRAG] Direct Python answer (no LLM needed)")
            return self._result(query_text, direct, "direct_python")

        # Step 3: LLM with filtered or full context
        if matched_indices:
            context_lines = [self.record_lines[i] for i in matched_indices[:10]]
            context = "\n".join(context_lines)
            method = "filtered"
        else:
            context = self.full_context
            method = "full_context"

        prompt = f"""You are a college staff directory assistant. Answer the question using ONLY the data below.

STRICT RULES:
1. Use ONLY data explicitly written below. Do NOT invent or guess.
2. If a specific field (phone, email, etc.) is NOT present for that person in the data below, say "That information is not available in the staff directory."
3. HOD = Head of the Department.
4. For lists, use numbered points.
5. Be concise and factual. No extra commentary.

STAFF DATA:
{context}

Question: {query_text}
Answer:"""

        n = len(matched_indices) if matched_indices else len(self.records)
        print(f"  [StaffRAG] {method}: {n} records, {len(prompt)} chars → LLM")
        try:
            ans = self.ollama.generate(prompt).strip()
            return self._result(query_text, ans, f"llm_{method}")
        except Exception as e:
            return self._result(query_text, f"LLM error: {e}", "error")

    # ─── Result builder ──────────────────────────────────────────────────────

    def _result(self, q: str, ans: str, method: str) -> Dict[str, Any]:
        return {
            "query": q,
            "answer": ans,
            "method": method,
        }
