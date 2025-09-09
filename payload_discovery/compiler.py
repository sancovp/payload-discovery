#!/usr/bin/env python3
"""
PayloadDiscovery Compiler - Convert structured directories to PayloadDiscovery configs.

Takes any directory structure with numbered markdown files and creates a complete
PayloadDiscovery JSON configuration that maps every single file.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .core import PayloadDiscovery, PayloadDiscoveryPiece, safe_write_config

logger = logging.getLogger(__name__)


@dataclass
class FileMapping:
    """Represents a discovered file and its extracted metadata."""
    filepath: Path
    filename: str
    sequence_number: int
    title: str
    content: str
    piece_type: str
    directory: Optional[str] = None


@dataclass
class CompilerConfig:
    """Configuration for PayloadDiscovery compilation."""
    domain_name: Optional[str] = None
    version: str = "v01" 
    description: str = ""


class PayloadDiscoveryCompiler:
    """
    Compiler that converts structured directories to PayloadDiscovery configs.
    
    Performs complete 1-to-1 mapping of every file in the source directory.
    """
    
    def __init__(self):
        self.file_mappings: List[FileMapping] = []
        self.sequence_pattern = re.compile(r'^(\d+)_')
        self.title_pattern = re.compile(r'^#\s+(.+)$', re.MULTILINE)
    
    def _extract_sequence_number(self, filename: str) -> Optional[int]:
        """Extract sequence number from filename like '00_Overview.md'."""
        match = self.sequence_pattern.match(filename)
        if match:
            return int(match.group(1))
        return None
    
    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from first # header in content."""
        match = self.title_pattern.search(content)
        if match:
            return match.group(1).strip()
        return "Untitled"
    
    def _categorize_by_filename(self, filename: str) -> Optional[str]:
        """Categorize piece type by filename patterns."""
        filename_lower = filename.lower()
        
        filename_patterns = {
            'readme': 'overview',
            'master_prompt': 'master_prompt', 
            'architecture': 'architecture',
            'overview': 'overview',
            'summary': 'summary',
            'example': 'example',
            'dsl': 'dsl',
            'visual': 'visual',
            'guide': 'guide'
        }
        
        for pattern, piece_type in filename_patterns.items():
            if pattern in filename_lower:
                return piece_type
        
        if 'quick_start' in filename_lower or 'quickstart' in filename_lower:
            return 'quickstart'
            
        return None
    
    def _categorize_by_directory(self, directory: Optional[str]) -> Optional[str]:
        """Categorize piece type by directory context."""
        if not directory:
            return None
            
        dir_lower = directory.lower()
        dir_patterns = {
            'instruction': 'instruction',
            'research': 'research', 
            'roadmap': 'roadmap',
            'test': 'test_case'
        }
        
        for pattern, piece_type in dir_patterns.items():
            if pattern in dir_lower:
                return piece_type
        
        return None
    
    def _categorize_by_content(self, content: str) -> Optional[str]:
        """Categorize piece type by content patterns."""
        content_lower = content.lower()
        
        if 'workflow' in content_lower and 'notation' in content_lower:
            return 'workflow'
        
        content_patterns = {
            'implementation': 'implementation',
            'architecture': 'architecture',
            'framework': 'framework', 
            'ontological': 'ontological'
        }
        
        for pattern, piece_type in content_patterns.items():
            if pattern in content_lower:
                return piece_type
        
        return None
    
    def _categorize_piece_type(self, filename: str, content: str, directory: Optional[str]) -> str:
        """Categorize the piece type based on filename, content, and directory."""
        # Try categorization by filename first
        piece_type = self._categorize_by_filename(filename)
        if piece_type:
            return piece_type
            
        # Then by directory context
        piece_type = self._categorize_by_directory(directory)
        if piece_type:
            return piece_type
            
        # Finally by content patterns
        piece_type = self._categorize_by_content(content)
        if piece_type:
            return piece_type
            
        # Default fallback
        return 'instruction'
    
    def _infer_dependencies(self, sequence_num: int, all_sequences: List[int]) -> List[int]:
        """Infer dependencies based on sequence order."""
        # Simple heuristic: depend on the previous sequence number if it exists
        if sequence_num > 0 and (sequence_num - 1) in all_sequences:
            return [sequence_num - 1]
        return []
    
    def _get_directory_name(self, md_file: Path, relative_to: Path) -> Optional[str]:
        """Get relative directory name for a markdown file."""
        relative_dir = md_file.parent.relative_to(relative_to)
        return str(relative_dir) if str(relative_dir) != '.' else None
    
    def _assign_sequence_number(self, filename: str, existing_mappings: List[FileMapping]) -> int:
        """Assign sequence number to file (numbered or auto-assigned)."""
        sequence_num = self._extract_sequence_number(filename)
        if sequence_num is None:
            # Assign high sequence numbers to non-numbered files
            sequence_num = 1000 + len([m for m in existing_mappings if m.sequence_number >= 1000])
        return sequence_num
    
    def _create_file_mapping(self, md_file: Path, content: str, sequence_num: int, dir_name: Optional[str]) -> FileMapping:
        """Create FileMapping object from file data."""
        filename = md_file.name
        title = self._extract_title_from_content(content)
        piece_type = self._categorize_piece_type(filename, content, dir_name)
        
        return FileMapping(
            filepath=md_file,
            filename=filename,
            sequence_number=sequence_num,
            title=title,
            content=content,
            piece_type=piece_type,
            directory=dir_name
        )
    
    def _process_markdown_file(self, md_file: Path, relative_to: Path, existing_mappings: List[FileMapping]) -> Optional[FileMapping]:
        """Process a single markdown file into a FileMapping."""
        try:
            content = md_file.read_text(encoding='utf-8')
            dir_name = self._get_directory_name(md_file, relative_to)
            sequence_num = self._assign_sequence_number(md_file.name, existing_mappings)
            
            mapping = self._create_file_mapping(md_file, content, sequence_num, dir_name)
            logger.debug(f"Mapped: {md_file} -> seq:{sequence_num}, type:{mapping.piece_type}")
            return mapping
            
        except Exception as e:
            logger.warning(f"Failed to process {md_file}: {e}")
            return None
    
    def _scan_directory(self, directory: Path, relative_to: Path) -> List[FileMapping]:
        """Scan a directory for markdown files and create mappings."""
        mappings = []
        
        for md_file in directory.rglob('*.md'):
            mapping = self._process_markdown_file(md_file, relative_to, mappings)
            if mapping:
                mappings.append(mapping)
        
        return mappings
    
    def _group_by_directory(self, mappings: List[FileMapping]) -> Tuple[List[FileMapping], Dict[str, List[FileMapping]]]:
        """Group mappings into root files and directory groups."""
        root_files = []
        directories = {}
        
        for mapping in mappings:
            if mapping.directory is None:
                root_files.append(mapping)
            else:
                if mapping.directory not in directories:
                    directories[mapping.directory] = []
                directories[mapping.directory].append(mapping)
        
        return root_files, directories
    
    def _create_payload_pieces(self, mappings: List[FileMapping]) -> List[PayloadDiscoveryPiece]:
        """Convert FileMapping objects to PayloadDiscoveryPiece objects."""
        all_sequences = [m.sequence_number for m in mappings]
        pieces = []
        
        for mapping in mappings:
            dependencies = self._infer_dependencies(mapping.sequence_number, all_sequences)
            
            piece = PayloadDiscoveryPiece(
                sequence_number=mapping.sequence_number,
                filename=mapping.filename,
                title=mapping.title,
                content=mapping.content,
                piece_type=mapping.piece_type,
                dependencies=dependencies
            )
            pieces.append(piece)
        
        return pieces
    
    def _resolve_config(self, source_dir: str, config: CompilerConfig) -> CompilerConfig:
        """Resolve configuration with defaults."""
        if config.domain_name is None:
            config.domain_name = Path(source_dir).name
        if not config.description:
            config.description = f"Compiled from {Path(source_dir).name}"
        return config
    
    def compile_directory(
        self,
        source_dir: str,
        config: CompilerConfig
    ) -> PayloadDiscovery:
        """
        Compile a structured directory to PayloadDiscovery configuration.
        
        Args:
            source_dir: Path to source directory to compile
            config: CompilerConfig with domain name, version, description
            
        Returns:
            PayloadDiscovery instance with complete mapping
        """
        source_path = Path(source_dir)
        if not source_path.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")
        
        config = self._resolve_config(source_dir, config)
        logger.info(f"Compiling directory: {source_path} -> domain: {config.domain_name}")
        
        # Scan all markdown files
        self.file_mappings = self._scan_directory(source_path, source_path)
        logger.info(f"Found {len(self.file_mappings)} markdown files to map")
        
        # Group by directory structure
        root_mappings, dir_mappings = self._group_by_directory(self.file_mappings)
        
        # Convert to PayloadDiscoveryPiece objects
        root_pieces = self._create_payload_pieces(root_mappings)
        
        directory_pieces = {}
        for dir_name, mappings in dir_mappings.items():
            directory_pieces[dir_name] = self._create_payload_pieces(mappings)
        
        # Determine entry point (lowest sequence number or README)
        entry_point = "README.md"
        if root_pieces:
            entry_piece = min(root_pieces, key=lambda p: p.sequence_number)
            entry_point = entry_piece.filename
        elif directory_pieces:
            # Find lowest sequence across all directories
            all_pieces = []
            for pieces in directory_pieces.values():
                all_pieces.extend(pieces)
            if all_pieces:
                entry_piece = min(all_pieces, key=lambda p: p.sequence_number)
                entry_point = entry_piece.filename
        
        # Create PayloadDiscovery instance
        payload_discovery = PayloadDiscovery(
            domain=config.domain_name,
            version=config.version,
            description=config.description,
            directories=directory_pieces,
            root_files=root_pieces,
            entry_point=entry_point
        )
        
        # Validate
        issues = payload_discovery.validate_sequence()
        if issues:
            logger.warning(f"Validation issues in compiled config: {issues}")
        
        logger.info(f"Successfully compiled {len(self.file_mappings)} files into PayloadDiscovery config")
        return payload_discovery
    
    def compile_and_save(
        self,
        source_dir: str,
        output_config: str,
        config: CompilerConfig
    ) -> Path:
        """
        Compile directory and save configuration to JSON file.
        
        Args:
            source_dir: Path to source directory to compile
            output_config: Path where to save the JSON config
            config: CompilerConfig with domain name, version, description
            
        Returns:
            Path to saved configuration file
        """
        payload_discovery = self.compile_directory(source_dir, config)
        return safe_write_config(payload_discovery, output_config)


def compile_to_payload_discovery(
    source_dir: str,
    output_config: str,
    domain_name: Optional[str] = None,
    version: str = "v01",
    description: str = ""
) -> Path:
    """
    Convenience function to compile a directory to PayloadDiscovery config.
    
    Args:
        source_dir: Path to source directory to compile
        output_config: Path where to save the JSON config  
        domain_name: Domain name (defaults to directory name)
        version: Version string
        description: System description
        
    Returns:
        Path to saved configuration file
        
    Example:
        compile_to_payload_discovery(
            "/tmp/3_pass_autonomous_research_system_v01",
            "/tmp/3_pass_payload_config.json",
            domain_name="3_pass_research_system",
            description="Autonomous research system using 3-pass workflow"
        )
    """
    config = CompilerConfig(
        domain_name=domain_name,
        version=version,
        description=description
    )
    compiler = PayloadDiscoveryCompiler()
    return compiler.compile_and_save(source_dir, output_config, config)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python compiler.py <source_dir> <output_config.json> [domain_name]")
        sys.exit(1)
    
    source_dir = sys.argv[1]
    output_config = sys.argv[2]
    domain_name = sys.argv[3] if len(sys.argv) > 3 else None
    
    result_path = compile_to_payload_discovery(source_dir, output_config, domain_name)
    print(f"✅ Compiled to: {result_path}")