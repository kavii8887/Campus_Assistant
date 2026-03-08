"""
textract_service.py — AWS Textract Table Extraction
====================================================
Deterministic table extraction from timetable images.

NO LLM USAGE. Pure AWS Textract parsing.

Requirements:
- boto3 installed
- AWS credentials configured in environment
- Textract analyze_document permission

Version: 1.0
"""

import boto3
from typing import Dict, List, Any, Optional
from collections import defaultdict


class TextractTableExtractor:
    """
    AWS Textract client for table extraction.
    Deterministic parsing with no ML inference beyond Textract.
    """
    
    def __init__(self):
        self.client = boto3.client('textract')
    
    def extract_tables_from_image(self, image_bytes: bytes) -> Dict[str, List[Dict[str, str]]]:
        """
        Extract timetable tables from image using AWS Textract.
        
        Args:
            image_bytes: Raw image bytes (PNG/JPG/PDF)
        
        Returns:
            Structured timetable dict:
            {
                "Monday": [
                    {"time": "9-10", "subject": "CCS342", "staff": "Dr.X", "room": "LAB1"},
                    ...
                ],
                "Tuesday": [...],
                ...
            }
        """
        # Call Textract
        response = self.client.analyze_document(
            Document={'Bytes': image_bytes},
            FeatureTypes=['TABLES']
        )
        
        # Parse blocks
        blocks = response.get('Blocks', [])
        
        # Extract tables
        tables = self._extract_tables(blocks)
        
        # Convert to timetable structure
        timetable = self._tables_to_timetable(tables)
        
        return timetable
    
    def _extract_tables(self, blocks: List[Dict]) -> List[List[List[str]]]:
        """
        Parse Textract blocks into table structures.
        
        Returns:
            List of tables, each table is a list of rows, each row is a list of cells.
        """
        # Build lookup maps
        block_map = {block['Id']: block for block in blocks}
        
        tables = []
        
        for block in blocks:
            if block['BlockType'] == 'TABLE':
                table = self._parse_table_block(block, block_map)
                if table:
                    tables.append(table)
        
        return tables
    
    def _parse_table_block(
        self,
        table_block: Dict,
        block_map: Dict[str, Dict]
    ) -> Optional[List[List[str]]]:
        """Parse a single TABLE block into rows and cells."""
        if 'Relationships' not in table_block:
            return None
        
        # Get CELL blocks
        cell_blocks = []
        for relationship in table_block['Relationships']:
            if relationship['Type'] == 'CHILD':
                for cell_id in relationship['Ids']:
                    if cell_id in block_map:
                        cell_block = block_map[cell_id]
                        if cell_block['BlockType'] == 'CELL':
                            cell_blocks.append(cell_block)
        
        if not cell_blocks:
            return None
        
        # Build table grid
        max_row = max(cell['RowIndex'] for cell in cell_blocks)
        max_col = max(cell['ColumnIndex'] for cell in cell_blocks)
        
        table = [['' for _ in range(max_col)] for _ in range(max_row)]
        
        for cell in cell_blocks:
            row_idx = cell['RowIndex'] - 1
            col_idx = cell['ColumnIndex'] - 1
            
            # Extract text from cell
            cell_text = self._extract_cell_text(cell, block_map)
            table[row_idx][col_idx] = cell_text.strip()
        
        return table
    
    def _extract_cell_text(
        self,
        cell_block: Dict,
        block_map: Dict[str, Dict]
    ) -> str:
        """Extract text content from a CELL block."""
        if 'Relationships' not in cell_block:
            return ''
        
        text_parts = []
        
        for relationship in cell_block['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    if child_id in block_map:
                        child_block = block_map[child_id]
                        if child_block['BlockType'] == 'WORD':
                            text_parts.append(child_block.get('Text', ''))
        
        return ' '.join(text_parts)
    
    def _tables_to_timetable(
        self,
        tables: List[List[List[str]]]
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Convert extracted tables to timetable structure.
        
        Detects header row and maps columns dynamically.
        Supports common timetable formats.
        """
        if not tables:
            return {}
        
        # Use first table (timetables are typically single-table documents)
        table = tables[0]
        
        if len(table) < 2:
            return {}
        
        # Detect header row (first row)
        header = table[0]
        header_normalized = [self._normalize_header(h) for h in header]
        
        # Map columns
        column_map = self._map_columns(header_normalized)
        
        # Parse rows
        timetable = defaultdict(list)
        
        for row in table[1:]:
            if not any(cell.strip() for cell in row):
                continue  # Skip empty rows
            
            entry = self._parse_row(row, column_map)
            
            if entry and 'day' in entry:
                day = entry.pop('day')
                timetable[day].append(entry)
        
        return dict(timetable)
    
    def _normalize_header(self, header: str) -> str:
        """Normalize header text for column mapping."""
        h = header.lower().strip()
        
        # Common variations
        if h in ['day', 'days', 'weekday']:
            return 'day'
        if h in ['time', 'timing', 'period', 'hour', 'hours']:
            return 'time'
        if h in ['subject', 'course', 'class', 'topic']:
            return 'subject'
        if h in ['staff', 'faculty', 'teacher', 'instructor', 'prof']:
            return 'staff'
        if h in ['room', 'venue', 'location', 'hall']:
            return 'room'
        
        return h
    
    def _map_columns(self, headers: List[str]) -> Dict[str, int]:
        """Map column indices to field names."""
        column_map = {}
        
        for idx, header in enumerate(headers):
            if header in ['day', 'time', 'subject', 'staff', 'room']:
                column_map[header] = idx
        
        return column_map
    
    def _parse_row(
        self,
        row: List[str],
        column_map: Dict[str, int]
    ) -> Optional[Dict[str, str]]:
        """Parse a single row into a timetable entry."""
        entry = {}
        
        for field, idx in column_map.items():
            if idx < len(row):
                value = row[idx].strip()
                if value:
                    entry[field] = value
        
        # Require at least day or time
        if not entry or ('day' not in entry and 'time' not in entry):
            return None
        
        return entry


def extract_tables_from_image(image_bytes: bytes) -> Dict[str, List[Dict[str, str]]]:
    """
    Public API for table extraction.
    
    Args:
        image_bytes: Raw image bytes
    
    Returns:
        Structured timetable dict
    """
    extractor = TextractTableExtractor()
    return extractor.extract_tables_from_image(image_bytes)