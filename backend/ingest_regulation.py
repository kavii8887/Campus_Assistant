"""
Regulation Ingestion Pipeline - Global, One Only
=================================================
Ingests university regulation document as semantic chunks.

CRITICAL RULES:
- Exactly ONE regulation allowed (overwrites existing)
- Global scope (no department metadata)
- Chunks by headings/articles
- Stored in: vector_db/global/regulation/

Usage:
    python ingest_regulation.py regulation.md

Version: 1.0
"""

import re
import hashlib
import argparse
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

from ollama_client import OllamaClient
from semantic_store import SemanticVectorStore
from vector_store_paths import VectorStorePaths


@dataclass
class RegulationChunkMetadata:
    """Metadata for regulation chunks."""
    chunk_id: str
    doc_id: str
    section_title: Optional[str]
    section_number: Optional[str]
    chunk_index: int
    word_count: int
    
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None


class RegulationParser:
    """Parse regulation document into sections."""
    
    def parse(self, content: str) -> List[Tuple[str, str, str]]:
        """
        Parse regulation into sections.
        
        Returns:
            List of (section_number, section_title, section_content)
        """
        sections = []
        
        # Pattern: ## 1.2.3 Section Title
        section_pattern = re.compile(
            r'^#{1,3}\s+([\d.]+)\s+(.+?)$',
            re.MULTILINE
        )
        
        matches = list(section_pattern.finditer(content))
        
        for i, match in enumerate(matches):
            section_num = match.group(1)
            section_title = match.group(2).strip()
            
            # Extract content between this section and next
            start = match.end()
            end = matches[i+1].start() if i+1 < len(matches) else len(content)
            section_content = content[start:end].strip()
            
            sections.append((section_num, section_title, section_content))
        
        return sections


class RegulationChunker:
    """Chunk regulation sections for embedding."""
    
    def __init__(self, chunk_size: int = 500):
        self.chunk_size = chunk_size
    
    def chunk_section(
        self,
        section_num: str,
        section_title: str,
        content: str,
        doc_id: str
    ) -> List[Tuple[str, RegulationChunkMetadata]]:
        """Chunk single regulation section."""
        chunks = []
        
        # Add section header to content
        full_content = f"{section_num} {section_title}\n\n{content}"
        
        words = full_content.split()
        
        for i in range(0, len(words), self.chunk_size):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            chunk_id = hashlib.sha256(
                f"{doc_id}:{section_num}:{i}".encode()
            ).hexdigest()[:16]
            
            metadata = RegulationChunkMetadata(
                chunk_id=chunk_id,
                doc_id=doc_id,
                section_title=section_title,
                section_number=section_num,
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


class RegulationIngestionPipeline:
    """
    Regulation ingestion orchestrator.
    
    Exactly ONE regulation allowed - overwrites existing.
    """
    
    def __init__(self):
        print("="*70)
        print("REGULATION INGESTION PIPELINE")
        print("="*70)
        print("Scope: GLOBAL (one regulation only)\n")
        
        # Initialize components
        self.paths = VectorStorePaths()
        self.ollama = OllamaClient()
        self.parser = RegulationParser()
        self.chunker = RegulationChunker(chunk_size=500)
        
        # Get collection details
        collection_name = self.paths.get_collection_name('regulation')
        persist_path = self.paths.get_persist_path('regulation')
        
        embedding_dim = self.ollama.get_embedding_dim()
        self.vector_store = SemanticVectorStore(
            collection_name=collection_name,
            embedding_dim=embedding_dim,
            persist_path=persist_path
        )
        
        print("✓ Pipeline ready\n")
    
    def ingest(self, markdown_path: str):
        """Ingest regulation document."""
        print("="*70)
        print("STARTING REGULATION INGESTION")
        print("="*70 + "\n")
        
        # Load
        print(f"[1/4] Loading: {markdown_path}")
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
        doc_id = Path(markdown_path).stem
        print(f"  Size: {len(content):,} chars\n")
        
        # Parse sections
        print(f"[2/4] Parsing sections...")
        sections = self.parser.parse(content)
        print(f"  Found {len(sections)} sections\n")
        
        # Chunk sections
        print(f"[3/4] Chunking sections...")
        all_chunks = []
        for section_num, section_title, section_content in sections:
            if len(section_content) > 50:
                chunks = self.chunker.chunk_section(
                    section_num=section_num,
                    section_title=section_title,
                    content=section_content,
                    doc_id=doc_id
                )
                all_chunks.extend(chunks)
        print(f"  Generated {len(all_chunks)} chunks\n")
        
        # Embed and store
        if all_chunks:
            print(f"[4/4] Generating embeddings and storing...")
            texts = [c[0] for c in all_chunks]
            embeddings = self.ollama.embed_batch(texts)
            
            # Convert metadata to dict format for storage
            chunks_with_dict_metadata = []
            for text, metadata in all_chunks:
                dict_metadata = {
                    'chunk_id': metadata.chunk_id,
                    'doc_id': metadata.doc_id,
                    'section_title': metadata.section_title,
                    'section_number': metadata.section_number,
                    'chunk_index': metadata.chunk_index,
                    'word_count': metadata.word_count,
                    'prev_chunk_id': metadata.prev_chunk_id,
                    'next_chunk_id': metadata.next_chunk_id,
                }
                chunks_with_dict_metadata.append((text, dict_metadata))
            
            self.vector_store.ingest_chunks(chunks_with_dict_metadata, embeddings)
        
        print(f"\n{'='*70}")
        print(f"✓ REGULATION INGESTION COMPLETE")
        print(f"{'='*70}")
        print(f"  Sections: {len(sections)}")
        print(f"  Chunks: {len(all_chunks)}")
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='Ingest regulation document')
    parser.add_argument('markdown_file', type=str, help='Regulation markdown file')
    
    args = parser.parse_args()
    
    if not Path(args.markdown_file).exists():
        print(f"❌ File not found: {args.markdown_file}")
        return
    
    pipeline = RegulationIngestionPipeline()
    pipeline.ingest(args.markdown_file)


if __name__ == "__main__":
    from typing import Optional
    main()