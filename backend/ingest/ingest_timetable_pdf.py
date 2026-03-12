"""
ingest_timetable_pdf.py — Timetable Ingestion via PDFPlumber
============================================================
Parses a highly structured Timetable PDF (e.g., CSE_timetable.pdf) 
into semantic chunks and ingests it into Qdrant for RAG.

Usage:
    venv/Scripts/python.exe ingest_timetable_pdf.py data/general/timetables/CSE_timetable.pdf --dept CSE
"""

import os
import sys
import uuid
import argparse
import pdfplumber
import requests
import numpy as np
from typing import List, Dict, Any, Tuple
from pathlib import Path

# Fix relative imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from semantic_vector_store import SemanticVectorStore

# Minimal Ollama Client inside ingest to match architecture
class OllamaClient:
    def __init__(self, embedding_model: str = "nomic-embed-text"):
        self.embedding_model = embedding_model
        self.embed_endpoint = "http://localhost:11434/api/embeddings"
    
    def embed_single(self, text: str) -> List[float]:
        response = requests.post(
            self.embed_endpoint,
            json={"model": self.embedding_model, "prompt": text}
        )
        return response.json()['embedding']
    
    def embed_batch(self, texts: List[str], batch_size: int = 10) -> np.ndarray:
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            for text in batch:
                embeddings.append(self.embed_single(text))
            
            if (i + batch_size) % 50 == 0:
                print(f"  Embedded {min(i+batch_size, len(texts))}/{len(texts)}", end='\r')
        
        print(f"  Embedded {len(texts)}/{len(texts)}")
        return np.array(embeddings)
    
    def get_embedding_dim(self) -> int:
        return len(self.embed_single("test"))

class TimetablePDFPipeline:
    def __init__(self, department: str):
        print("="*70)
        print("TIMETABLE PDF INGESTION PIPELINE")
        print("="*70)
        print(f"Department: {department}\n")
        
        self.department = department.upper()
        self.ollama = OllamaClient()
        
        collection_name = f"{self.department}_timetable"
        persist_path = f"./vector_db/{self.department}/timetable"
        
        print(f"✓ Collection: {collection_name}")
        print(f"✓ Path: {persist_path}\n")
        
        embedding_dim = self.ollama.get_embedding_dim()
        self.semantic_store = SemanticVectorStore(
            collection_name=collection_name,
            embedding_dim=embedding_dim,
            persist_path=persist_path
        )
        
    def _clean_cell(self, cell):
        if not cell:
            return ""
        return str(cell).replace('\n', ' ').strip()

    def process_pdf(self, pdf_path: str):
        print(f"[1/4] Reading PDF: {pdf_path}")
        chunks = []
        chunk_counter = 0
        
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]
            tables = page.extract_tables()
            
            if not tables:
                print("❌ No tables found in PDF.")
                return
            
            # Processing Table 0: Weekly Timetable
            if len(tables) > 0:
                print("[2/4] Parsing Weekly Schedule...")
                grid = tables[0]
                headers = [self._clean_cell(c) for c in grid[0]]
                
                # Daily schedules
                for row_idx in range(1, len(grid)):
                    row = [self._clean_cell(c) for c in grid[row_idx]]
                    if not row or not row[0]:
                        continue
                    
                    day = row[0]
                    day_schedule = []
                    
                    for col_idx in range(1, len(headers)):
                        if col_idx < len(row):
                            period_time = headers[col_idx]
                            subject = row[col_idx]
                            
                            # Skip if subject is empty
                            if subject:
                                day_schedule.append(f"During Period {period_time}, the subject is '{subject}'.")
                    
                    if day_schedule:
                        chunk_text = f"{self.department} Department Timetable for {day}:\n" + "\n".join(day_schedule)
                        metadata = {
                            "source": Path(pdf_path).name,
                            "type": "TIMETABLE_DAILY",
                            "department": self.department,
                            "day": day,
                            "chunk_index": chunk_counter
                        }
                        chunks.append((chunk_text, metadata))
                        chunk_counter += 1

            # Processing Table 1: Practicals / Map
            if len(tables) > 1:
                print("[3/4] Parsing Practical / Subject Mapping...")
                pr_grid = tables[1]
                pr_headers = [self._clean_cell(c).upper() for c in pr_grid[0]]
                
                for row_idx in range(1, len(pr_grid)):
                    row = [self._clean_cell(c) for c in pr_grid[row_idx]]
                    if not row or not row[0]:
                        continue
                    
                    subject_code = row[0] if len(row) > 0 else "Unknown Code"
                    subject_name = row[1] if len(row) > 1 else "Unknown Subject"
                    staff_incharge = row[2] if len(row) > 2 else "Unknown Staff"
                    assist_staff = row[3] if len(row) > 3 else "Unknown Assistant"
                    venue = row[4] if len(row) > 4 else "Unknown Venue"
                    
                    chunk_text = (
                        f"{self.department} Department Practical Subject Details:\n"
                        f"Subject Code: {subject_code}\n"
                        f"Subject Name: {subject_name}\n"
                        f"Staff Incharge: {staff_incharge}\n"
                        f"Assistant Staff: {assist_staff}\n"
                        f"Venue / Lab Room: {venue}"
                    )
                    
                    metadata = {
                        "source": Path(pdf_path).name,
                        "type": "TIMETABLE_PRACTICAL",
                        "department": self.department,
                        "subject_code": subject_code,
                        "subject_name": subject_name,
                        "chunk_index": chunk_counter
                    }
                    chunks.append((chunk_text, metadata))
                    chunk_counter += 1

        print(f"  Generated {len(chunks)} contextual chunks.\n")
        
        if chunks:
            print("[4/4] Generating Embeddings and saving to Vector Store...")
            texts = [c[0] for c in chunks]
            embeddings = self.ollama.embed_batch(texts)
            self.semantic_store.ingest_chunks(chunks, embeddings)
            print("✓ Successfully ingested timetable into Qdrant.")
        else:
            print("❌ Error generating chunks.")

def main():
    parser = argparse.ArgumentParser(description='Ingest timetable PDF using pdfplumber')
    parser.add_argument('pdf_file', type=str, help='Timetable PDF file')
    parser.add_argument('--dept', type=str, required=True, help='Department')
    args = parser.parse_args()
    
    if not Path(args.pdf_file).exists():
        print(f"❌ File not found: {args.pdf_file}")
        sys.exit(1)
        
    pipeline = TimetablePDFPipeline(args.dept)
    pipeline.process_pdf(args.pdf_file)

if __name__ == '__main__':
    main()
