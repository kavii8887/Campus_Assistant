"""
ingest_timetable_textract.py — AWS Textract Timetable Ingestion
=================================================================
Ingests timetable images using AWS Textract table extraction.

CRITICAL RULES:
- Department-scoped (CSE, ECE, etc.)
- Metadata: department, year, semester, section
- Stored in: vector_db/{DEPT}/timetable/structured/
- NO LLM usage — pure Textract parsing

Usage:
    python -m ingest.ingest_timetable_textract timetable.png --dept CSE --year 2 --semester odd --section A

Version: 1.0
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any

from textract_service import extract_tables_from_image
from vector_store_paths import VectorStorePaths


class TimetableTextractPipeline:
    """
    AWS Textract-based timetable ingestion.
    
    Deterministic table extraction and structured JSON storage.
    """
    
    def __init__(self, department: str):
        print("=" * 70)
        print("TIMETABLE INGESTION PIPELINE (AWS TEXTRACT)")
        print("=" * 70)
        print(f"Department: {department}\n")
        
        self.department = department.upper()
        self.paths = VectorStorePaths()
        
        # Ensure structured timetable directory exists
        self._ensure_structured_dir()
        
        print("✓ Pipeline ready\n")
    
    def _ensure_structured_dir(self):
        """Create structured timetable directory if missing."""
        base_path = Path(self.paths.base_path)
        structured_path = base_path / self.department / "timetable" / "structured"
        structured_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Structured timetable directory: {structured_path}")
    
    def ingest_image(
        self,
        image_path: str,
        year: int,
        semester: str,
        section: str
    ):
        """
        Ingest timetable from image file.
        
        Args:
            image_path: Path to timetable image (PNG/JPG/PDF)
            year: Year (1-4)
            semester: Semester (odd/even)
            section: Section (A, B, etc.)
        """
        print("=" * 70)
        print("STARTING TIMETABLE INGESTION (TEXTRACT)")
        print("=" * 70 + "\n")
        
        # Load image
        print(f"[1/4] Loading image: {image_path}")
        image_path_obj = Path(image_path)
        
        if not image_path_obj.exists():
            print(f"❌ File not found: {image_path}")
            return
        
        with open(image_path_obj, 'rb') as f:
            image_bytes = f.read()
        
        print(f"  Size: {len(image_bytes):,} bytes")
        print(f"  Format: {image_path_obj.suffix}\n")
        
        # Extract tables with Textract
        print(f"[2/4] Extracting tables with AWS Textract...")
        try:
            timetable_data = extract_tables_from_image(image_bytes)
            print(f"  ✓ Extracted {len(timetable_data)} days")
            
            total_entries = sum(len(entries) for entries in timetable_data.values())
            print(f"  ✓ Total entries: {total_entries}\n")
        
        except Exception as e:
            print(f"❌ Textract extraction failed: {e}")
            return
        
        # Build structured timetable
        print(f"[3/4] Building structured timetable...")
        structured_timetable = {
            "metadata": {
                "department": self.department,
                "year": year,
                "semester": semester,
                "section": section
            },
            "timetable": timetable_data
        }
        print(f"  ✓ Structure built\n")
        
        # Save to JSON
        print(f"[4/4] Saving to structured storage...")
        output_path = self._get_output_path(year, semester, section)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(structured_timetable, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Saved: {output_path}\n")
        
        # Summary
        print("=" * 70)
        print("✓ TIMETABLE INGESTION COMPLETE")
        print("=" * 70)
        print(f"  Department: {self.department}")
        print(f"  Year: {year}")
        print(f"  Semester: {semester.upper()}")
        print(f"  Section: {section}")
        print(f"  Days: {len(timetable_data)}")
        print(f"  Entries: {total_entries}")
        print(f"  File: {output_path}")
        print("=" * 70 + "\n")
    
    def _get_output_path(self, year: int, semester: str, section: str) -> Path:
        """Generate output path for structured timetable JSON."""
        base_path = Path(self.paths.base_path)
        structured_dir = base_path / self.department / "timetable" / "structured"
        
        filename = f"year{year}_{semester}_{section}.json"
        return structured_dir / filename


def main():
    parser = argparse.ArgumentParser(
        description='Ingest timetable using AWS Textract'
    )
    parser.add_argument(
        'image_file',
        type=str,
        help='Timetable image file (PNG/JPG/PDF)'
    )
    parser.add_argument(
        '--dept',
        type=str,
        required=True,
        help='Department code (CSE, ECE, etc.)'
    )
    parser.add_argument(
        '--year',
        type=int,
        required=True,
        help='Year (1-4)'
    )
    parser.add_argument(
        '--semester',
        type=str,
        required=True,
        help='Semester (odd/even)'
    )
    parser.add_argument(
        '--section',
        type=str,
        required=True,
        help='Section (A, B, etc.)'
    )
    
    args = parser.parse_args()
    
    # Validation
    if not Path(args.image_file).exists():
        print(f"❌ File not found: {args.image_file}")
        return
    
    if args.year not in [1, 2, 3, 4]:
        print(f"❌ Invalid year: {args.year}. Must be 1-4")
        return
    
    if args.semester.lower() not in ['odd', 'even']:
        print(f"❌ Invalid semester: {args.semester}. Must be 'odd' or 'even'")
        return
    
    # Run pipeline
    pipeline = TimetableTextractPipeline(department=args.dept)
    pipeline.ingest_image(
        image_path=args.image_file,
        year=args.year,
        semester=args.semester.lower(),
        section=args.section.upper()
    )


if __name__ == "__main__":
    main()