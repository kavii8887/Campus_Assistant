"""
Staff Ingestion Pipeline - Department-Scoped
=============================================
Ingests staff directory JSON with metadata.

CRITICAL RULES:
- Department-scoped (CSE, ECE, etc.)
- Input: JSON (manually normalized)
- Semantic search enabled on staff profiles
- Stored in: vector_db/{DEPT}/staff/

Usage:
    python ingest_staff.py staff.json --dept CSE

JSON Format:
[
    {
        "name": "Dr. John Doe",
        "designation": "Professor",
        "email": "john.doe@university.edu",
        "phone": "123-456-7890",
        "specialization": "Machine Learning, AI",
        "courses": ["CS3301", "CS4401"]
    }
]

Version: 1.0
"""

import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass

from ollama_client import OllamaClient
from semantic_store import SemanticVectorStore
from vector_store_paths import VectorStorePaths


@dataclass
class StaffChunkMetadata:
    """Metadata for staff profile chunks."""
    chunk_id: str
    doc_id: str
    department: str
    staff_name: str
    designation: Optional[str]
    email: Optional[str]
    chunk_index: int
    word_count: int
    
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None


class StaffChunker:
    """Chunk staff profiles for embedding."""
    
    def chunk_staff_profiles(
        self,
        staff_data: List[Dict[str, Any]],
        department: str,
        doc_id: str
    ) -> List[Tuple[str, StaffChunkMetadata]]:
        """
        Chunk staff profiles.
        
        Each staff member = 1 chunk.
        """
        chunks = []
        
        for idx, staff in enumerate(staff_data):
            # Build text representation
            lines = [f"STAFF PROFILE - {department}"]
            lines.append(f"Name: {staff.get('name', 'Unknown')}")
            
            if staff.get('designation'):
                lines.append(f"Designation: {staff['designation']}")
            
            if staff.get('email'):
                lines.append(f"Email: {staff['email']}")
            
            if staff.get('phone'):
                lines.append(f"Phone: {staff['phone']}")
            
            if staff.get('specialization'):
                lines.append(f"Specialization: {staff['specialization']}")
            
            if staff.get('courses'):
                courses = ', '.join(staff['courses'])
                lines.append(f"Courses: {courses}")
            
            if staff.get('cabin'):
                lines.append(f"Cabin: {staff['cabin']}")
            
            if staff.get('office_hours'):
                lines.append(f"Office Hours: {staff['office_hours']}")
            
            chunk_text = '\n'.join(lines)
            
            chunk_id = hashlib.sha256(
                f"{doc_id}:{department}:{staff.get('name', idx)}".encode()
            ).hexdigest()[:16]
            
            metadata = StaffChunkMetadata(
                chunk_id=chunk_id,
                doc_id=doc_id,
                department=department,
                staff_name=staff.get('name', 'Unknown'),
                designation=staff.get('designation'),
                email=staff.get('email'),
                chunk_index=idx,
                word_count=len(chunk_text.split()),
            )
            
            chunks.append((chunk_text, metadata))
        
        # Link chunks
        for i in range(len(chunks)):
            if i > 0:
                chunks[i][1].prev_chunk_id = chunks[i-1][1].chunk_id
            if i < len(chunks) - 1:
                chunks[i][1].next_chunk_id = chunks[i+1][1].chunk_id
        
        return chunks


class StaffIngestionPipeline:
    """
    Staff ingestion orchestrator.
    
    Department-scoped staff directory.
    """
    
    def __init__(self, department: str):
        print("="*70)
        print("STAFF INGESTION PIPELINE")
        print("="*70)
        print(f"Department: {department}\n")
        
        # Initialize components
        self.department = department.upper()
        self.paths = VectorStorePaths()
        self.ollama = OllamaClient()
        self.chunker = StaffChunker()
        
        # Get collection details
        collection_name = self.paths.get_collection_name('staff', self.department)
        persist_path = self.paths.get_persist_path('staff', self.department)
        
        embedding_dim = self.ollama.get_embedding_dim()
        self.vector_store = SemanticVectorStore(
            collection_name=collection_name,
            embedding_dim=embedding_dim,
            persist_path=persist_path
        )
        
        print("✓ Pipeline ready\n")
    
    def ingest(self, json_path: str):
        """Ingest staff JSON file."""
        print("="*70)
        print("STARTING STAFF INGESTION")
        print("="*70 + "\n")
        
        # Load JSON
        print(f"[1/3] Loading: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            staff_data = json.load(f)
        doc_id = Path(json_path).stem
        print(f"  Found {len(staff_data)} staff members\n")
        
        # Chunk
        print(f"[2/3] Creating staff profile chunks...")
        chunks = self.chunker.chunk_staff_profiles(
            staff_data=staff_data,
            department=self.department,
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
                    'staff_name': metadata.staff_name,
                    'designation': metadata.designation,
                    'email': metadata.email,
                    'chunk_index': metadata.chunk_index,
                    'word_count': metadata.word_count,
                    'prev_chunk_id': metadata.prev_chunk_id,
                    'next_chunk_id': metadata.next_chunk_id,
                }
                chunks_with_dict_metadata.append((text, dict_metadata))
            
            self.vector_store.ingest_chunks(chunks_with_dict_metadata, embeddings)
        
        print(f"\n{'='*70}")
        print(f"✓ STAFF INGESTION COMPLETE")
        print(f"{'='*70}")
        print(f"  Staff members: {len(staff_data)}")
        print(f"  Chunks: {len(chunks)}")
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Ingest staff directory JSON')
    parser.add_argument('json_file', type=str, help='Staff directory JSON file')
    parser.add_argument('--dept', type=str, required=True, help='Department code (CSE, ECE, etc.)')
    
    args = parser.parse_args()
    
    if not Path(args.json_file).exists():
        print(f"❌ File not found: {args.json_file}")
        return
    
    pipeline = StaffIngestionPipeline(department=args.dept)
    pipeline.ingest(json_path=args.json_file)


if __name__ == "__main__":
    from typing import Optional
    main()