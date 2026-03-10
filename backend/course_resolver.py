# course_resolver.py
"""
Course code resolver for ingestion pipeline
"""

import re
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class CourseCodeResolver:
    """Bidirectional course code ↔ name resolver"""
    
    WORD_NORMALIZATIONS = {
        'programming': 'programming',
        'programme': 'programming',
        'programs': 'programming',
        'databases': 'database',
        'networks': 'network',
        'systems': 'system',
        'principles': 'principles',
        'principle': 'principles',
        'foundations': 'foundation',
        'fundamentals': 'fundamental',
        'introduction': 'intro',
        'advanced': 'adv',
        'laboratory': 'lab',
        'practical': 'lab',
        'datastructures': 'data structures',
        'datastructure': 'data structures',
    }
    
    STRUCTURAL_KEYWORDS = {
        'list', 'show', 'display', 'get', 'fetch', 'retrieve',
        'unit', 'units', 'topic', 'topics', 'chapter', 'chapters',
        'what', 'how', 'when', 'where', 'which', 'tell', 'give',
        'credits', 'credit', 'hours', 'syllabus', 'objectives',
        'outcomes', 'outcome', 'textbook', 'textbooks', 'reference', 'references',
        'first', 'second', 'third', 'fourth', 'fifth',
        'about', 'explain', 'describe', 'summarize', 'summary',
        'name', 'code', 'course', 'subject', 'subjects', 'exercises', 'exercise',
        'content', 'section', 'sections', 'module', 'modules',
        'total', 'sum', 'all'
    }
    
    def __init__(self, department: str = "CSE"):
        self.department = department
        self.code_to_name: Dict[str, str] = {}
        self.name_to_code: Dict[str, str] = {}
        self.code_to_credits: Dict[str, str] = {}
        self.normalized_to_code: Dict[str, str] = {}
        self.acronym_to_code: Dict[str, str] = {}
        self.keyword_to_codes: Dict[str, List[str]] = defaultdict(list)
    
    def load_mappings(self, mapping_text: str):
        """Load course mappings from text file"""
        lines = mapping_text.strip().split('\n')
        count = 0
        
        for line in lines:
            line = line.strip()
            if not line or '→' not in line:
                continue
            
            parts = line.split('→')
            if len(parts) != 3:
                continue
            
            code = parts[0].strip().upper()
            name = parts[1].strip()
            credits = parts[2].strip()
            
            self.code_to_name[code] = name
            self.name_to_code[name] = code
            self.code_to_credits[code] = credits
            
            normalized_name = self._normalize_name(name)
            self.normalized_to_code[normalized_name] = code
            
            keywords = self._extract_keywords(name)
            for keyword in keywords:
                self.keyword_to_codes[keyword].append(code)
            
            count += 1
        
        print(f"✓ Loaded {count} course mappings")
    
    def parse_code_structure(self, code: str) -> Dict[str, Optional[str]]:
        """Parse course code structure"""
        code_upper = code.upper()
        
        dept_match = re.match(r'^([A-Z]{2,4})', code_upper)
        department = dept_match.group(1) if dept_match else None
        
        year_match = re.search(r'(\d)', code_upper)
        year = int(year_match.group(1)) if year_match else None
        
        semester = None
        if year:
            semester = 'odd' if year % 2 == 1 else 'even'
        
        return {
            'department': department,
            'year': year,
            'semester': semester
        }
    
    def get_name_from_code(self, code: str) -> Optional[str]:
        if not code:
            return None
        return self.code_to_name.get(code.upper())
    
    def get_credits_from_code(self, code: str) -> Optional[str]:
        if not code:
            return None
        code_upper = code.upper()
        credits = self.code_to_credits.get(code_upper)
        if not credits or credits == "0":
            return None
        return credits
    
    def resolve_code(
        self,
        query: str,
        allow_fuzzy: bool = True
    ) -> Tuple[Optional[str], Optional[str], List[str]]:
        """Resolve course code from query"""
        query_upper = query.upper()
        query_lower = query.lower()
        
        code_match = re.search(r'\b([A-Z]{2,4})\s*(\d{3,5})\b', query, re.IGNORECASE)
        if code_match:
            code = f"{code_match.group(1)}{code_match.group(2)}".upper()
            if code in self.code_to_name:
                return code, self.code_to_name[code], []
            else:
                return None, None, [f"Course code {code} not found in database"]
        
        for name, code in self.name_to_code.items():
            if name.lower() == query_lower:
                return code, name, []
        
        query_words = query_upper.split()
        for word in query_words:
            if word in self.acronym_to_code:
                code = self.acronym_to_code[word]
                return code, self.code_to_name.get(code, "Unknown"), []
        
        query_clean = query_upper.strip()
        if query_clean in self.acronym_to_code:
            code = self.acronym_to_code[query_clean]
            return code, self.code_to_name.get(code, "Unknown"), []
        
        normalized_query = self._normalize_name(query)
        if normalized_query in self.normalized_to_code:
            code = self.normalized_to_code[normalized_query]
            return code, self.code_to_name[code], []
        
        if allow_fuzzy:
            query_keywords = self._extract_keywords(query)
            substantive_keywords = [
                kw for kw in query_keywords 
                if kw not in self.STRUCTURAL_KEYWORDS
            ]
            
            if substantive_keywords:
                candidates = self._score_candidates(substantive_keywords)
                
                if not candidates:
                    return None, None, []
                
                top_score = candidates[0][1]
                tied = [c for c, s in candidates if s == top_score]
                
                if len(tied) > 1:
                    ambiguities = [
                        f"{self.code_to_name[c]} ({c})" for c in tied
                    ]
                    return None, None, ambiguities
                
                if len(candidates) > 1 and top_score <= 3:
                    top_candidates = [c for c, s in candidates[:min(3, len(candidates))]]
                    ambiguities = [
                        f"{self.code_to_name[c]} ({c})" for c in top_candidates
                    ]
                    return None, None, ambiguities
                
                best_code = candidates[0][0]
                return best_code, self.code_to_name[best_code], []
        
        return None, None, []
    
    def resolve_multiple_codes(self, query: str) -> List[Tuple[str, str]]:
        """Detect and resolve multiple course mentions"""
        results = []
        seen_codes = set()
        
        and_pattern = r'(.+?)\s+and\s+(.+?)(?:\s+(?:syllabus|course|code|credits?))?$'
        match = re.search(and_pattern, query, re.IGNORECASE)
        
        if match:
            part1 = match.group(1).strip()
            part2 = match.group(2).strip()
            
            for prefix in ['credits of', 'credits for', 'credit of', 'credit for', 'compare', 'comparison', 'the']:
                part1 = re.sub(f'^{prefix}\\s+', '', part1, flags=re.IGNORECASE).strip()
                part2 = re.sub(f'^{prefix}\\s+', '', part2, flags=re.IGNORECASE).strip()
            
            code1, name1, _ = self.resolve_code(part1)
            if code1 and code1 not in seen_codes:
                results.append((code1, name1))
                seen_codes.add(code1)
            
            code2, name2, _ = self.resolve_code(part2)
            if code2 and code2 not in seen_codes:
                results.append((code2, name2))
                seen_codes.add(code2)
        
        return results
    
    def get_courses_by_semester(self, semester_num: int) -> List[Tuple[str, str]]:
        """Fetch all courses that belong to a specific semester."""
        results = []
        for code, name in self.code_to_name.items():
            # For AU Regulation 2021 codes, the format is usually XX3YZZ where Y is the semester.
            # E.g., GE3151 -> Sem 1, CS3451 -> Sem 4
            match = re.search(r'[A-Z]{2,3}3(\d)', code.upper())
            if match:
                sem_digit = int(match.group(1))
                if sem_digit == semester_num:
                    results.append((code, name))
        return results
    
    def _normalize_name(self, name: str) -> str:
        normalized = name.lower()
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        words = normalized.split()
        normalized_words = []
        for word in words:
            normalized_words.append(
                self.WORD_NORMALIZATIONS.get(word, word)
            )
        filler = {'the', 'and', 'of', 'in', 'to', 'for', 'with', 'a', 'an'}
        normalized_words = [w for w in normalized_words if w not in filler]
        normalized = ' '.join(normalized_words)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _extract_keywords(self, text: str) -> List[str]:
        normalized = self._normalize_name(text)
        words = normalized.split()
        keywords = [w for w in words if len(w) >= 4]
        return keywords
    
    def _score_candidates(self, query_keywords: List[str]) -> List[Tuple[str, int]]:
        candidates = defaultdict(int)
        
        for keyword in query_keywords:
            if keyword in self.keyword_to_codes:
                for code in self.keyword_to_codes[keyword]:
                    candidates[code] += 2
            
            for indexed_keyword, codes in self.keyword_to_codes.items():
                if keyword in indexed_keyword or indexed_keyword in keyword:
                    for code in codes:
                        candidates[code] += 1
        
        sorted_candidates = sorted(
            candidates.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_candidates