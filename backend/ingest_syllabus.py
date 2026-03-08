"""
Syllabus Ingestion Pipeline - Department-Scoped (PHASE 3)
==========================================================
ONE-TIME EXECUTION: Ingests academic syllabus data.
"""

import sys
from pathlib import Path

# ✅ Ensure project root is importable
ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT))

import re
import hashlib
import time
import json
import argparse
import requests
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

# =============================================================================
# ⭐⭐⭐ FIXED IMPORTS — DO NOT CHANGE LOGIC ⭐⭐⭐
# =============================================================================

# Your models + store live INSIDE structured_store package
from structured_store import (
    StructuredAcademicStore,
    CourseMetadata,
    CourseObjectives,
    CourseOutcomes,
    CourseTextbooks,
    CourseReferences,
    CourseLabExercises,
    UnitInfo,
    Textbook,
    Reference,
    LabExercise,
    ChunkMetadata,
)

from semantic_vector_store import SemanticVectorStore
from course_resolver import CourseCodeResolver

  # ⭐ FIXED NAME



# =============================================================================
# OLLAMA CLIENT (INTEGRATED)
# =============================================================================

class OllamaClient:
    """Minimal Ollama client for embeddings."""
    
    def __init__(self, embedding_model: str = "nomic-embed-text"):
        self.embedding_model = embedding_model
        self.embed_endpoint = "http://localhost:11434/api/embeddings"
    
    def embed_single(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        response = requests.post(
            self.embed_endpoint,
            json={"model": self.embedding_model, "prompt": text}
        )
        return response.json()['embedding']
    
    def embed_batch(self, texts: List[str], batch_size: int = 10) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            for text in batch:
                emb = self.embed_single(text)
                embeddings.append(emb)
            
            if (i + batch_size) % 50 == 0:
                print(f"  Embedded {min(i+batch_size, len(texts))}/{len(texts)}", end='\r')
        
        print(f"  Embedded {len(texts)}/{len(texts)}")
        return np.array(embeddings)
    
    def get_embedding_dim(self) -> int:
        """Get embedding dimension."""
        test_embed = self.embed_single("test")
        return len(test_embed)


# =============================================================================
# MARKDOWN CLEANER
# =============================================================================

class MarkdownCleaner:
    """Clean raw markdown syllabi."""
    
    @staticmethod
    def clean(content: str) -> str:
        """Remove noise while preserving structure."""
        content = re.sub(r'^(?:Page\s+)?\d+\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\s*[-–—]\s*\d+\s*[-–—]\s*$', '', content, flags=re.MULTILINE)
        content = re.sub(r' {2,}', ' ', content)
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        content = '\n'.join(line.rstrip() for line in content.split('\n'))
        content = re.sub(r'^\s*[•·◦]\s+', '- ', content, flags=re.MULTILINE)
        content = re.sub(r'^(#{1,6})([^\s#])', r'\1 \2', content, flags=re.MULTILINE)
        return content.strip()


# =============================================================================
# SYLLABUS PARSER
# =============================================================================

class SyllabusParser:
    """Parse syllabus into structured sections."""
    
    def __init__(self, course_resolver: CourseCodeResolver):
        self.course_resolver = course_resolver
        self.course_pattern = re.compile(r'\b([A-Z]{2,4})\s*(\d{3,5})\b')
    
    def parse_document(self, content: str, doc_id: str) -> Dict[str, Any]:
        course_sections = self._split_by_course(content)
        parsed_courses = {}
        
        for course_code, course_text in course_sections.items():
            parsed = self._parse_course_section(course_code, course_text)
            parsed_courses[course_code] = parsed
        
        return {'courses': parsed_courses}
    
    def _split_by_course(self, content: str) -> Dict[str, str]:
        courses = {}
        lines = content.split('\n')
        current_course = None
        current_lines = []
        
        for line in lines:
            match = self.course_pattern.search(line)
            
            if match and (line.startswith('#') or '**' in line or len(line) < 100):
                if current_course and current_lines:
                    courses[current_course] = '\n'.join(current_lines)
                
                current_course = f"{match.group(1)}{match.group(2)}".upper()
                current_lines = [line]
            elif current_course:
                current_lines.append(line)
        
        if current_course and current_lines:
            courses[current_course] = '\n'.join(current_lines)
        
        return courses
    
    def _parse_course_section(self, course_code: str, text: str) -> Dict[str, Any]:
        result = {
            'metadata': self._extract_metadata(course_code, text),
            'objectives': self._extract_objectives(course_code, text),
            'outcomes': self._extract_outcomes(course_code, text),
            'textbooks': self._extract_textbooks(course_code, text),
            'references': self._extract_references(course_code, text),
            'lab_exercises': self._extract_lab_exercises(course_code, text),
            'units': [],
            'unit_contents': {}
        }
        
        units_data = self._extract_units(course_code, text)
        result['units'] = units_data['units']
        result['unit_contents'] = units_data['contents']
        
        return result
    
    def _extract_metadata(self, course_code: str, text: str) -> CourseMetadata:
        course_name = self.course_resolver.get_name_from_code(course_code)
        
        if not course_name:
            lines = text.split('\n')
            for line in lines[:20]:
                if course_code in line:
                    clean = re.sub(r'[#*_\[\]]', '', line)
                    clean = re.sub(r'\s+', ' ', clean).strip()
                    
                    if '-' in clean or '–' in clean or ':' in clean:
                        parts = re.split(r'[-–—:]', clean)
                        for part in parts:
                            if course_code not in part and len(part) > 3:
                                course_name = part.strip()
                                break
                    
                    if course_name:
                        break
        
        credits = self.course_resolver.get_credits_from_code(course_code)
        
        if not credits:
            for line in text.split('\n')[:30]:
                if 'L' in line and 'T' in line and 'P' in line and 'C' in line:
                    match = re.search(r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', line)
                    if match:
                        credits = f"{match.group(1)}-{match.group(2)}-{match.group(3)}-{match.group(4)}"
                        break
        
        structure = self.course_resolver.parse_code_structure(course_code)
        
        return CourseMetadata(
            course_code=course_code,
            course_name=course_name or "Unknown Course",
            credits=credits or "0",
            department=structure.get('department'),
            year=structure.get('year'),
            semester=structure.get('semester'),
        )
    
    def _extract_objectives(self, course_code: str, text: str) -> Optional[CourseObjectives]:
        pattern = r'\*{0,2}COURSE OBJECTIVES?\*{0,2}(.*?)(?=\*{0,2}(?:COURSE OUTCOMES?|UNIT|TEXT BOOKS?|$))'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if not match:
            return None
        
        section = match.group(1)
        objectives = []
        lines = section.split('\n')
        current_obj = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if re.match(r'^[\d•\-]\s*\.?\s*', line):
                if current_obj:
                    objectives.append(current_obj.strip())
                current_obj = re.sub(r'^[\d•\-]\s*\.?\s*', '', line)
            else:
                current_obj += " " + line
        
        if current_obj:
            objectives.append(current_obj.strip())
        
        if objectives:
            return CourseObjectives(course_code=course_code, objectives=objectives)
        
        return None
    
    def _extract_outcomes(self, course_code: str, text: str) -> Optional[CourseOutcomes]:
        pattern = r'\*{0,2}COURSE OUTCOMES?\*{0,2}(.*?)(?=\*{0,2}(?:UNIT|TEXT BOOKS?|REFERENCES|$))'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if not match:
            return None
        
        section = match.group(1)
        outcomes = []
        lines = section.split('\n')
        current_outcome = ""
        current_code = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            co_match = re.match(r'(CO\d+)\s*:?\s*(.*)', line, re.IGNORECASE)
            if co_match:
                if current_code and current_outcome:
                    outcomes.append({'code': current_code, 'description': current_outcome.strip()})
                current_code = co_match.group(1).upper()
                current_outcome = co_match.group(2)
            else:
                current_outcome += " " + line
        
        if current_code and current_outcome:
            outcomes.append({'code': current_code, 'description': current_outcome.strip()})
        
        if outcomes:
            return CourseOutcomes(course_code=course_code, outcomes=outcomes)
        
        return None
    
    def _extract_textbooks(self, course_code: str, text: str) -> Optional[CourseTextbooks]:
        pattern = r'\*{0,2}TEXT\s*BOOKS?\*{0,2}(.*?)(?=\*{0,2}(?:REFERENCES|UNIT|$))'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if not match:
            return None
        
        section = match.group(1)
        textbooks = []
        items = re.split(r'\n\s*\d+\.\s*', section)
        
        for item in items[1:]:
            item = item.strip()
            if len(item) < 10:
                continue
            textbooks.append(Textbook(title=item))
        
        if textbooks:
            return CourseTextbooks(course_code=course_code, textbooks=textbooks)
        
        return None
    
    def _extract_references(self, course_code: str, text: str) -> Optional[CourseReferences]:
        pattern = r'\*{0,2}REFERENCES\*{0,2}(.*?)(?=\*{0,2}(?:UNIT|$))'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if not match:
            return None
        
        section = match.group(1)
        references = []
        items = re.split(r'\n\s*\d+\.\s*', section)
        
        for item in items[1:]:
            item = item.strip()
            if len(item) < 10:
                continue
            references.append(Reference(title=item))
        
        if references:
            return CourseReferences(course_code=course_code, references=references)
        
        return None
    
    def _extract_lab_exercises(self, course_code: str, text: str) -> Optional[CourseLabExercises]:
        pattern = r'\*{0,2}(?:LIST OF EXERCISES|LAB EXERCISES|EXPERIMENTS)\*{0,2}(.*?)(?=\*{0,2}(?:TOTAL|$))'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if not match:
            return None
        
        section = match.group(1)
        exercises = []
        items = re.split(r'\n\s*(\d+)\.\s*', section)
        
        for i in range(1, len(items), 2):
            if i+1 < len(items):
                num = int(items[i])
                title = items[i+1].strip().split('\n')[0]
                exercises.append(LabExercise(number=num, title=title))
        
        if exercises:
            return CourseLabExercises(course_code=course_code, exercises=exercises)
        
        return None
    
    def _extract_units(self, course_code: str, text: str) -> Dict[str, Any]:
        unit_pattern = re.compile(r'\*{0,2}UNIT\s+([IVX]+)\*{0,2}\s*[:\-]?\s*(.*?)$', re.MULTILINE)
        units = []
        contents = {}
        matches = list(unit_pattern.finditer(text))
        
        for i, match in enumerate(matches):
            unit_num = match.group(1)
            unit_title = match.group(2).strip()
            start = match.end()
            end = matches[i+1].start() if i+1 < len(matches) else len(text)
            content = text[start:end]
            
            for boundary in ['**TEXT BOOKS', '**REFERENCES', '**TOTAL']:
                if boundary in content:
                    content = content[:content.index(boundary)]
                    break
            
            units.append(UnitInfo(course_code=course_code, unit_number=unit_num, unit_title=unit_title))
            contents[unit_num] = content.strip()
        
        return {'units': units, 'contents': contents}


# =============================================================================
# UNIT CHUNKER
# =============================================================================

class UnitChunker:
    """Chunk unit content for embedding."""
    
    def __init__(self, chunk_size: int = 400):
        self.chunk_size = chunk_size
    
    def chunk_unit_content(
        self, course_code: str, course_name: str, unit_number: str,
        unit_title: str, content: str, doc_id: str
    ) -> List[Tuple[str, ChunkMetadata]]:
        chunks = []
        words = content.split()
        
        for i in range(0, len(words), self.chunk_size):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunk_id = hashlib.sha256(f"{doc_id}:{course_code}:{unit_number}:{i}".encode()).hexdigest()[:16]
            
            metadata = ChunkMetadata(
                chunk_id=chunk_id,
                doc_id=doc_id,
                primary_course_code=course_code,
                course_name=course_name,
                unit_number=unit_number,
                unit_title=unit_title,
                section_path=f"{course_code} > Unit {unit_number}",
                chunk_index=i // self.chunk_size,
                word_count=len(chunk_words),
                char_start=i * self.chunk_size,
                char_end=(i + len(chunk_words)) * self.chunk_size,
                prev_chunk_id=None,
                next_chunk_id=None
            )
            
            chunks.append((chunk_text, metadata))
        
        for i in range(len(chunks)):
            if i > 0:
                chunks[i][1].prev_chunk_id = chunks[i-1][1].chunk_id
            if i < len(chunks) - 1:
                chunks[i][1].next_chunk_id = chunks[i+1][1].chunk_id
        
        return chunks


# =============================================================================
# ACRONYM GENERATOR
# =============================================================================

class AcronymGenerator:
    """
    Generate comprehensive acronym mappings for runtime use.
    Handles both theory and lab courses with multiple variants.
    """
    
    @staticmethod
    def _is_lab_course(name: str) -> bool:
        """Check if course name indicates a lab/practical course."""
        lab_keywords = ['lab', 'laboratory', 'practical', 'workshop', 'studio']
        name_lower = name.lower()
        return any(keyword in name_lower for keyword in lab_keywords)
    
    @staticmethod
    def _generate_base_acronym(name: str) -> str:
        """Generate base acronym from course name (first letters of significant words)."""
        filler_words = {
            'the', 'and', 'of', 'in', 'to', 'for', 'with', 'a', 'an',
            'on', 'at', 'by', 'from', 'as', 'is', 'are', 'was', 'were',
            'lab', 'laboratory', 'practical', 'workshop', 'studio'  # Exclude these from base acronym
        }
        
        words = name.lower().split()
        significant_words = [w for w in words if w not in filler_words and len(w) > 0]
        
        if not significant_words:
            return ""
        
        # Take first letter of each significant word
        acronym = ''.join([w[0].upper() for w in significant_words])
        return acronym
    
    @staticmethod
    def generate_acronyms(parsed_courses: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate comprehensive acronym → code mappings.
        
        For theory courses:
        - Base acronym (e.g., "OOP")
        
        For lab courses:
        - Base acronym with "L" suffix (e.g., "OOPL")
        - Base acronym with " LAB" (e.g., "OOP LAB")
        - Full name variations
        
        Returns:
            Dict mapping acronyms to course codes
        """
        acronym_map = {}
        
        for course_code, course_data in parsed_courses.items():
            metadata = course_data.get('metadata')
            if not metadata or not metadata.course_name:
                continue
            
            name = metadata.course_name
            is_lab = AcronymGenerator._is_lab_course(name)
            
            if is_lab:
                # Lab course - generate multiple variants
                # 1. Remove "Lab", "Laboratory", "Practical" to get theory name
                theory_name = re.sub(
                    r'\s*(?:lab|laboratory|practical|workshop|studio)\s*',
                    ' ',
                    name,
                    flags=re.IGNORECASE
                ).strip()
                theory_name = re.sub(r'\s+', ' ', theory_name)
                
                base_acronym = AcronymGenerator._generate_base_acronym(theory_name)
                
                if base_acronym:
                    # Add variants:
                    # 1. Base with "L" suffix: "OOPL"
                    lab_acronym_short = base_acronym + "L"
                    if lab_acronym_short not in acronym_map:
                        acronym_map[lab_acronym_short] = course_code
                    
                    # 2. Base with " LAB": "OOP LAB"
                    lab_acronym_long = base_acronym + " LAB"
                    if lab_acronym_long not in acronym_map:
                        acronym_map[lab_acronym_long] = course_code
                    
                    # 3. Base with " LABORATORY": "OOP LABORATORY"
                    lab_acronym_full = base_acronym + " LABORATORY"
                    if lab_acronym_full not in acronym_map:
                        acronym_map[lab_acronym_full] = course_code
                    
                    # 4. Full theory name + "LAB": "OBJECT ORIENTED PROGRAMMING LAB"
                    if theory_name:
                        full_lab_name = theory_name.upper() + " LAB"
                        if full_lab_name not in acronym_map:
                            acronym_map[full_lab_name] = course_code
            else:
                # Theory course - just base acronym
                base_acronym = AcronymGenerator._generate_base_acronym(name)
                
                if base_acronym and base_acronym not in acronym_map:
                    acronym_map[base_acronym] = course_code
            
            # Also add full course name (uppercase) as acronym for exact matching
            full_name_key = name.upper()
            if full_name_key not in acronym_map:
                acronym_map[full_name_key] = course_code
        
        return acronym_map


# =============================================================================
# INGESTION ORCHESTRATOR
# =============================================================================

class IngestionPipeline:
    """Complete ingestion orchestrator - DEPARTMENT-SCOPED."""
    
    def __init__(self, department: str, structured_store_path: str, mapping_file: Optional[str] = None):
        print("="*70)
        print("SYLLABUS INGESTION PIPELINE v3.2")
        print("="*70)
        print(f"Department: {department}\n")
        
        self.department = department.upper()
        
        self.course_resolver = CourseCodeResolver(department=self.department)
        if mapping_file and Path(mapping_file).exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                self.course_resolver.load_mappings(f.read())
        
        self.ollama = OllamaClient()
        self.structured_store = StructuredAcademicStore(structured_store_path)
        
        # CRITICAL: Match runtime paths exactly
        collection_name = f"{self.department}_syllabus"
        persist_path = f"./vector_db/{self.department}/syllabus"
        
        print(f"✓ Collection: {collection_name}")
        print(f"✓ Path: {persist_path}\n")
        
        embedding_dim = self.ollama.get_embedding_dim()
        self.semantic_store = SemanticVectorStore(
            collection_name=collection_name,
            embedding_dim=embedding_dim,
            persist_path=persist_path
        )
        
        self.cleaner = MarkdownCleaner()
        self.parser = SyllabusParser(self.course_resolver)
        self.chunker = UnitChunker(chunk_size=400)
        
        print("✓ Pipeline ready\n")

    def ingest_document(self, markdown_path: str, doc_id: Optional[str] = None):
        start_time = time.time()
        
        print("="*70)
        print("STARTING INGESTION")
        print("="*70 + "\n")
        
        print(f"[1/6] Loading: {markdown_path}")
        with open(markdown_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        doc_id = doc_id or Path(markdown_path).stem
        print(f"  Size: {len(raw_content):,} chars\n")
        
        print(f"[2/6] Cleaning markdown...")
        cleaned = self.cleaner.clean(raw_content)
        print(f"  Cleaned: {len(cleaned):,} chars\n")
        
        print(f"[3/6] Parsing structured sections...")
        parsed = self.parser.parse_document(cleaned, doc_id)
        print(f"  Found {len(parsed['courses'])} courses\n")
        
        # ENHANCED: Generate comprehensive acronyms
        print(f"[3.5/6] Generating acronyms...")
        acronym_map = AcronymGenerator.generate_acronyms(parsed['courses'])
        
        acronym_file = Path(f"{self.department}_acronyms.json")
        with open(acronym_file, 'w', encoding='utf-8') as f:
            json.dump(acronym_map, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Generated {len(acronym_map)} acronym variants → {acronym_file}")
        print(f"  Sample mappings:")
        for i, (acronym, code) in enumerate(list(acronym_map.items())[:5]):
            print(f"    {acronym} → {code}")
        print()
        
        print(f"[4/6] Storing structured data...")
        for course_code, course_data in parsed['courses'].items():
            if course_data['metadata']:
                self.structured_store.store_metadata(course_data['metadata'])
            if course_data['objectives']:
                self.structured_store.store_objectives(course_data['objectives'])
            if course_data['outcomes']:
                self.structured_store.store_outcomes(course_data['outcomes'])
            if course_data['textbooks']:
                self.structured_store.store_textbooks(course_data['textbooks'])
            if course_data['references']:
                self.structured_store.store_references(course_data['references'])
            if course_data['lab_exercises']:
                self.structured_store.store_lab_exercises(course_data['lab_exercises'])
            if course_data['units']:
                self.structured_store.store_units(course_code, course_data['units'])
        print(f"  ✓ Structured data stored\n")
        
        print(f"[5/6] Chunking unit content...")
        all_chunks = []
        for course_code, course_data in parsed['courses'].items():
            metadata = course_data['metadata']
            for unit_num, unit_content in course_data['unit_contents'].items():
                unit_info = next((u for u in course_data['units'] if u.unit_number == unit_num), None)
                
                if unit_info and len(unit_content) > 50:
                    chunks = self.chunker.chunk_unit_content(
                        course_code=course_code,
                        course_name=metadata.course_name,
                        unit_number=unit_num,
                        unit_title=unit_info.unit_title,
                        content=unit_content,
                        doc_id=doc_id
                    )
                    all_chunks.extend(chunks)
        print(f"  Generated {len(all_chunks)} chunks\n")
        
        if all_chunks:
            print(f"[6/6] Generating embeddings and storing...")
            texts = [c[0] for c in all_chunks]
            embeddings = self.ollama.embed_batch(texts)
            self.semantic_store.ingest_chunks(all_chunks, embeddings)
        
        elapsed = time.time() - start_time
        
        print(f"\n{'='*70}")
        print(f"✓ INGESTION COMPLETE")
        print(f"{'='*70}")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Department: {self.department}")
        print(f"  Courses: {len(parsed['courses'])}")
        print(f"  Acronyms: {len(acronym_map)}")
        print(f"  Chunks: {len(all_chunks)}")
        print(f"{'='*70}\n")


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Ingest academic syllabus')
    parser.add_argument('markdown_file', type=str, help='Syllabus markdown file')
    parser.add_argument('--dept', type=str, required=True, help='Department code (CSE, ECE, etc.)')
    parser.add_argument('--structured-path', type=str, default='./structured_store')
    parser.add_argument('--mapping-file', type=str, default='course_mappings.txt')
    
    args = parser.parse_args()
    
    if not Path(args.markdown_file).exists():
        print(f"❌ File not found: {args.markdown_file}")
        return
    
    pipeline = IngestionPipeline(
        department=args.dept,
        structured_store_path=args.structured_path,
        mapping_file=args.mapping_file if Path(args.mapping_file).exists() else None
    )
    
    pipeline.ingest_document(args.markdown_file)


if __name__ == "__main__":
    main()