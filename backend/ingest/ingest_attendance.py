"""
Attendance Ingestion Pipeline - Department-Scoped (PHASE 4)
============================================================
Ingests attendance Excel files with metadata.

CRITICAL RULES:
- Department-scoped (CSE, ECE, etc.)
- Metadata: department, year, semester, date
- Parses Excel into semantic chunks
- Stored in: vector_db/{DEPT}/attendance/
- PHASE 4: Raw Excel ALSO stored in vector_db/{DEPT}/attendance/raw/

Usage:
    python ingest_attendance.py attendance.xlsx --dept CSE --year 2 --semester odd --date 2024-02-09

Version: 1.1 (Phase 4: Raw file storage)
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import hashlib
import argparse
from typing import List, Tuple, Optional
from dataclasses import dataclass
import pandas as pd

from ollama_client import OllamaClient
from semantic_vector_store import SemanticVectorStore
from vector_store_paths import VectorStorePaths

@dataclass
class AttendanceChunkMetadata:
    """Metadata for attendance chunks."""
    chunk_id: str
    doc_id: str
    department: str
    year: int
    semester: str
    date: str
    chunk_index: int
    word_count: int
    
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None


class AttendanceParser:
    """Parse Excel attendance file."""
    
    def parse(self, excel_path: str) -> str:
        """
        Parse Excel file into text representation.
        
        Returns:
            Text representation of attendance data
        """
        df = pd.read_excel(excel_path)
        
        # Build text representation
        lines = []
        lines.append("ATTENDANCE RECORD\n")
        
        # Add column headers
        lines.append("Columns: " + ", ".join(df.columns.astype(str)))
        lines.append("")
        
        # Add rows
        for idx, row in df.iterrows():
            row_text = " | ".join([f"{col}: {val}" for col, val in row.items()])
            lines.append(row_text)
        
        return "\n".join(lines)


class AttendanceChunker:
    """Chunk attendance content for embedding."""
    
    def __init__(self, chunk_size: int = 300):
        self.chunk_size = chunk_size
    
    def chunk_attendance(
        self,
        content: str,
        department: str,
        year: int,
        semester: str,
        date: str,
        doc_id: str
    ) -> List[Tuple[str, AttendanceChunkMetadata]]:
        """Chunk attendance content."""
        chunks = []
        
        # Add metadata header
        header = f"Attendance - {department} Year {year} {semester.upper()} Semester Date: {date}\n\n"
        full_content = header + content
        
        words = full_content.split()
        
        for i in range(0, len(words), self.chunk_size):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunk_id = hashlib.sha256(
                f"{doc_id}:{department}:{year}:{semester}:{date}:{i}".encode()
            ).hexdigest()[:16]
            
            metadata = AttendanceChunkMetadata(
                chunk_id=chunk_id,
                doc_id=doc_id,
                department=department,
                year=year,
                semester=semester,
                date=date,
                chunk_index=i // self.chunk_size,
                word_count=len(chunk_words),
            )
            
            chunks.append((chunk_text, metadata))
        
        # Link chunks
        for i in range(len(chunks)):
            if i > 0:
                chunks[i][1].prev_chunk_id = chunks[i-1][1].chunk_id
            if i < len(chunks) - 1:
                chunks[i][1].next_chunk_id = chunks[i+1][1].chunk_id
        
        return chunks


class AttendanceIngestionPipeline:
    """
    Attendance ingestion orchestrator.
    
    Department-scoped with year/semester/date metadata.
    PHASE 4: Stores raw Excel for deterministic calculations.
    """
    
    def __init__(self, department: str):
        print("="*70)
        print("ATTENDANCE INGESTION PIPELINE (PHASE 4)")
        print("="*70)
        print(f"Department: {department}\n")
        
        # Initialize components
        self.department = department.upper()
        self.paths = VectorStorePaths()
        self.ollama = OllamaClient()
        self.parser = AttendanceParser()
        self.chunker = AttendanceChunker(chunk_size=300)
        
        # Get collection details
        collection_name = self.paths.get_collection_name('attendance', self.department)
        persist_path = self.paths.get_persist_path('attendance', self.department)
        
        embedding_dim = self.ollama.get_embedding_dim()
        self.vector_store = SemanticVectorStore(
            collection_name=collection_name,
            embedding_dim=embedding_dim,
            persist_path=persist_path
        )
        
        print("✓ Pipeline ready\n")
    
    def ingest(
        self,
        excel_path: str,
        year: int,
        semester: str,
        date: str
    ):
        """Ingest attendance Excel file."""
        print("="*70)
        print("STARTING ATTENDANCE INGESTION")
        print("="*70 + "\n")
        
        # PHASE 4: Copy raw Excel to raw folder FIRST
        doc_id = Path(excel_path).stem
        raw_dir = Path(self.paths.get_persist_path('attendance', self.department)) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename with metadata
        raw_filename = f"{doc_id}_year{year}_{semester}_{date}.xlsx"
        raw_dest = raw_dir / raw_filename
        
        print(f"[1/4] Copying raw Excel to: {raw_dest}")
        import shutil
        shutil.copy2(excel_path, raw_dest)
        print(f"  ✓ Raw file stored for deterministic calculations\n")
        
        # Parse Excel
        print(f"[2/4] Parsing Excel: {excel_path}")
        content = self.parser.parse(excel_path)
        print(f"  Parsed {len(content):,} chars")
        print(f"  Metadata: Year {year}, {semester.upper()} Semester, Date: {date}\n")
        
        # Chunk
        print(f"[3/4] Chunking attendance...")
        chunks = self.chunker.chunk_attendance(
            content=content,
            department=self.department,
            year=year,
            semester=semester,
            date=date,
            doc_id=doc_id
        )
        print(f"  Generated {len(chunks)} chunks\n")
        
        # Embed and store
        if chunks:
            print(f"[4/4] Generating embeddings and storing...")
            texts = [c[0] for c in chunks]
            embeddings = self.ollama.embed_batch(texts)
            
            # Convert metadata to dict format
            chunks_with_dict_metadata = []
            for text, metadata in chunks:
                dict_metadata = {
                    'chunk_id': metadata.chunk_id,
                    'doc_id': metadata.doc_id,
                    'department': metadata.department,
                    'year': metadata.year,
                    'semester': metadata.semester,
                    'date': metadata.date,
                    'chunk_index': metadata.chunk_index,
                    'word_count': metadata.word_count,
                    'prev_chunk_id': metadata.prev_chunk_id,
                    'next_chunk_id': metadata.next_chunk_id,
                }
                chunks_with_dict_metadata.append((text, dict_metadata))
            
            self.vector_store.ingest_chunks(chunks_with_dict_metadata, embeddings)
        
        print(f"\n{'='*70}")
        print(f"✓ ATTENDANCE INGESTION COMPLETE")
        print(f"{'='*70}")
        print(f"  Raw Excel: {raw_dest}")
        print(f"  Chunks: {len(chunks)}")
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Ingest attendance Excel file')
    parser.add_argument('excel_file', type=str, help='Attendance Excel file')
    parser.add_argument('--dept', type=str, required=True, help='Department code (CSE, ECE, etc.)')
    parser.add_argument('--year', type=int, required=True, help='Year (1-4)')
    parser.add_argument('--semester', type=str, required=True, help='Semester (odd/even)')
    parser.add_argument('--date', type=str, required=True, help='Date (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if not Path(args.excel_file).exists():
        print(f"❌ File not found: {args.excel_file}")
        return
    
    if args.year not in [1, 2, 3, 4]:
        print(f"❌ Invalid year: {args.year}. Must be 1-4")
        return
    
    if args.semester.lower() not in ['odd', 'even']:
        print(f"❌ Invalid semester: {args.semester}. Must be 'odd' or 'even'")
        return
    
    pipeline = AttendanceIngestionPipeline(department=args.dept)
    pipeline.ingest(
        excel_path=args.excel_file,
        year=args.year,
        semester=args.semester.lower(),
        date=args.date
    )


if __name__ == "__main__":
    from typing import Optional
    main()