"""
Timetable Ingestion Pipeline - Department-Scoped
=================================================
Ingests OCR-extracted timetable text with metadata.

CRITICAL RULES:
- Department-scoped (CSE, ECE, etc.)
- Metadata: department, year, semester, section
- Chunks by day/time slots
- Stored in: vector_db/{DEPT}/timetable/

Usage:
    python ingest_timetable.py timetable.txt --dept CSE --year 2 --semester odd --section A

Version: 1.0
"""

import hashlib
import argparse
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from ollama_client import OllamaClient
from semantic_vector_store import SemanticVectorStore
from vector_store_paths import VectorStorePaths


@dataclass
class TimetableChunkMetadata:
    """Metadata for timetable chunks."""
    chunk_id: str
    doc_id: str
    department: str
    year: int
    semester: str
    section: str
    chunk_index: int
    word_count: int
    
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None


class TimetableChunker:
    """Chunk timetable content for embedding."""
    
    def __init__(self, chunk_size: int = 300):
        self.chunk_size = chunk_size
    
    def chunk_timetable(
        self,
        content: str,
        department: str,
        year: int,
        semester: str,
        section: str,
        doc_id: str
    ) -> List[Tuple[str, TimetableChunkMetadata]]:
        """Chunk timetable content."""
        chunks = []
        
        # Add metadata header to content
        header = f"Timetable - {department} Year {year} {semester.upper()} Semester Section {section}\n\n"
        full_content = header + content
        
        words = full_content.split()
        
        for i in range(0, len(words), self.chunk_size):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunk_id = hashlib.sha256(
                f"{doc_id}:{department}:{year}:{semester}:{section}:{i}".encode()
            ).hexdigest()[:16]
            
            metadata = TimetableChunkMetadata(
                chunk_id=chunk_id,
                doc_id=doc_id,
                department=department,
                year=year,
                semester=semester,
                section=section,
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


class TimetableIngestionPipeline:
    """
    Timetable ingestion orchestrator.
    
    Department-scoped with year/semester/section metadata.
    """
    
    def __init__(self, department: str):
        print("="*70)
        print("TIMETABLE INGESTION PIPELINE")
        print("="*70)
        print(f"Department: {department}\n")
        
        # Initialize components
        self.department = department.upper()
        self.paths = VectorStorePaths()
        self.ollama = OllamaClient()
        self.chunker = TimetableChunker(chunk_size=300)
        
        # Get collection details
        collection_name = self.paths.get_collection_name('timetable', self.department)
        persist_path = self.paths.get_persist_path('timetable', self.department)
        
        embedding_dim = self.ollama.get_embedding_dim()
        self.vector_store = SemanticVectorStore(
            collection_name=collection_name,
            embedding_dim=embedding_dim,
            persist_path=persist_path
        )
        
        print("✓ Pipeline ready\n")
    
    def ingest(
        self,
        text_path: str,
        year: int,
        semester: str,
        section: str
    ):
        """Ingest timetable text file."""
        print("="*70)
        print("STARTING TIMETABLE INGESTION")
        print("="*70 + "\n")
        
        # Load
        print(f"[1/3] Loading: {text_path}")
        with open(text_path, 'r', encoding='utf-8') as f:
            content = f.read()
        doc_id = Path(text_path).stem
        print(f"  Size: {len(content):,} chars")
        print(f"  Metadata: Year {year}, {semester.upper()} Semester, Section {section}\n")
        
        # Chunk
        print(f"[2/3] Chunking timetable...")
        chunks = self.chunker.chunk_timetable(
            content=content,
            department=self.department,
            year=year,
            semester=semester,
            section=section,
            doc_id=doc_id
        )
        print(f"  Generated {len(chunks)} chunks\n")
        
        # Embed and store
        if chunks:
            print(f"[3/3] Generating embeddings and storing...")
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
                    'section': metadata.section,
                    'chunk_index': metadata.chunk_index,
                    'word_count': metadata.word_count,
                    'prev_chunk_id': metadata.prev_chunk_id,
                    'next_chunk_id': metadata.next_chunk_id,
                }
                chunks_with_dict_metadata.append((text, dict_metadata))
            
            self.vector_store.ingest_chunks(chunks_with_dict_metadata, embeddings)
        
        print(f"\n{'='*70}")
        print(f"✓ TIMETABLE INGESTION COMPLETE")
        print(f"{'='*70}")
        print(f"  Chunks: {len(chunks)}")
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Ingest timetable')
    parser.add_argument('text_file', type=str, help='Timetable text file (OCR-extracted)')
    parser.add_argument('--dept', type=str, required=True, help='Department code (CSE, ECE, etc.)')
    parser.add_argument('--year', type=int, required=True, help='Year (1-4)')
    parser.add_argument('--semester', type=str, required=True, help='Semester (odd/even)')
    parser.add_argument('--section', type=str, required=True, help='Section (A, B, etc.)')
    
    args = parser.parse_args()
    
    if not Path(args.text_file).exists():
        print(f"❌ File not found: {args.text_file}")
        return
    
    if args.year not in [1, 2, 3, 4]:
        print(f"❌ Invalid year: {args.year}. Must be 1-4")
        return
    
    if args.semester.lower() not in ['odd', 'even']:
        print(f"❌ Invalid semester: {args.semester}. Must be 'odd' or 'even'")
        return
    
    pipeline = TimetableIngestionPipeline(department=args.dept)
    pipeline.ingest(
        text_path=args.text_file,
        year=args.year,
        semester=args.semester.lower(),
        section=args.section.upper()
    )


if __name__ == "__main__":
    main()