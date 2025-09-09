"""
PayloadDiscovery Core - Models and functions for creating numbered instruction systems.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from pydantic_stack_core import RenderablePiece
import logging

logger = logging.getLogger(__name__)


class PayloadDiscoveryPiece(BaseModel):
    """
    A single numbered instruction file in a PayloadDiscovery sequence.
    
    This represents one file in the numbered chain that an agent must traverse.
    Each piece builds on previous pieces to create progressive knowledge.
    """
    
    sequence_number: int = Field(..., description="Order in sequence (0-based)")
    filename: str = Field(..., description="Output filename (e.g., '00_Overview.md')")
    title: str = Field(..., description="Human-readable title")
    content: str = Field(..., description="The actual content/instructions")
    piece_type: str = Field(
        default="instruction",
        description="Type: overview, guide, synthesis, example, dsl, architecture, etc."
    )
    dependencies: List[int] = Field(
        default_factory=list,
        description="Sequence numbers that must be read before this piece"
    )
    
    def render_to_file(self, directory: Path) -> Path:
        """Write this piece to a file in the given directory."""
        filepath = directory / self.filename
        filepath.write_text(self.content)
        logger.debug(f"Wrote piece {self.sequence_number} to {filepath}")
        return filepath


class PayloadDiscovery(RenderablePiece):
    """
    Complete PayloadDiscovery system that generates numbered instruction directories.
    
    This model can:
    1. Be created/edited as JSON by maker agents
    2. Render to a complete filesystem structure
    3. Recreate structures like the 3_pass_autonomous_research_system
    
    Example:
        # Load from JSON
        pd = PayloadDiscovery.from_json("config.json")
        
        # Render to filesystem
        pd.render_to_directory("/tmp/my_system")
        
        # Export to JSON for editing
        json_str = pd.to_json()
    """
    
    domain: str = Field(..., description="Domain name (e.g., '3_pass_autonomous_research_system')")
    version: str = Field(default="v01", description="Version identifier")
    description: str = Field(default="", description="System description")
    
    # Directory structure: dirname -> list of pieces
    directories: Dict[str, List[PayloadDiscoveryPiece]] = Field(
        default_factory=dict,
        description="Subdirectories with their numbered files"
    )
    
    # Root level files (README, ARCHITECTURE, etc.)
    root_files: List[PayloadDiscoveryPiece] = Field(
        default_factory=list,
        description="Files at the root level"
    )
    
    # Entry point for agents
    entry_point: str = Field(
        default="README.md",
        description="Where agents should start reading"
    )
    
    def _render_header(self) -> List[str]:
        """Render header section."""
        lines = [f"# {self.domain} {self.version}"]
        if self.description:
            lines.append(f"\n{self.description}\n")
        lines.append("\n## Structure:")
        lines.append(f"Entry: {self.entry_point}")
        return lines
    
    def _render_files_list(self, pieces: List[PayloadDiscoveryPiece], prefix: str = "  - ") -> List[str]:
        """Render a list of files."""
        return [f"{prefix}{p.filename}: {p.title}" 
                for p in sorted(pieces, key=lambda p: p.sequence_number)]
    
    def render(self) -> str:
        """
        Render as a string representation of the directory structure.
        For actual filesystem rendering, use render_to_directory().
        """
        lines = self._render_header()
        
        if self.root_files:
            lines.append("\nRoot files:")
            lines.extend(self._render_files_list(self.root_files))
        
        for dirname, pieces in self.directories.items():
            lines.append(f"\n{dirname}/:")
            lines.extend(self._render_files_list(pieces))
        
        return "\n".join(lines)
    
    def _create_base_directory(self, base_path: str) -> Path:
        """Create and return the base directory."""
        base_dir = Path(base_path) / f"{self.domain}_{self.version}"
        base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Rendering PayloadDiscovery to {base_dir}")
        return base_dir
    
    def _write_directory_pieces(self, base_dir: Path, dirname: str, pieces: List[PayloadDiscoveryPiece]):
        """Write pieces to a subdirectory."""
        subdir = base_dir / dirname
        subdir.mkdir(parents=True, exist_ok=True)
        for piece in pieces:
            piece.render_to_file(subdir)
    
    def render_to_directory(self, base_path: str) -> Path:
        """
        Render the complete PayloadDiscovery system to a filesystem directory.
        
        Args:
            base_path: Base directory path (will be created if doesn't exist)
            
        Returns:
            Path to the created directory
        """
        base_dir = self._create_base_directory(base_path)
        
        for piece in self.root_files:
            piece.render_to_file(base_dir)
        
        for dirname, pieces in self.directories.items():
            self._write_directory_pieces(base_dir, dirname, pieces)
        
        logger.info(f"Successfully rendered {len(self.root_files)} root files and {len(self.directories)} directories")
        return base_dir
    
    def to_json(self, indent: int = 2) -> str:
        """Export to JSON string for editing by maker agents."""
        return self.model_dump_json(indent=indent)
    
    @classmethod
    def from_json(cls, json_path: str) -> "PayloadDiscovery":
        """
        Load PayloadDiscovery from a JSON file.
        
        Args:
            json_path: Path to JSON configuration file
            
        Returns:
            PayloadDiscovery instance
        """
        with open(json_path, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    def _get_all_filenames(self) -> List[str]:
        """Get all filenames from root and directories."""
        all_files = [p.filename for p in self.root_files]
        for pieces in self.directories.values():
            all_files.extend([p.filename for p in pieces])
        return all_files
    
    def _get_all_sequence_numbers(self) -> set:
        """Get all sequence numbers from all pieces."""
        all_numbers = {p.sequence_number for p in self.root_files}
        for pieces in self.directories.values():
            all_numbers.update(p.sequence_number for p in pieces)
        return all_numbers
    
    def _check_dependencies(self, pieces: List[PayloadDiscoveryPiece], all_numbers: set) -> List[str]:
        """Check if dependencies reference valid sequence numbers."""
        issues = []
        for piece in pieces:
            for dep in piece.dependencies:
                if dep not in all_numbers:
                    issues.append(f"Piece {piece.filename} depends on non-existent sequence number {dep}")
        return issues
    
    def validate_sequence(self) -> List[str]:
        """
        Validate that the sequence is well-formed.
        
        Returns:
            List of validation warnings/errors (empty if valid)
        """
        issues = []
        
        # Check for duplicate filenames
        all_files = self._get_all_filenames()
        if len(all_files) != len(set(all_files)):
            issues.append("Duplicate filenames detected")
        
        # Check dependencies are valid
        all_numbers = self._get_all_sequence_numbers()
        issues.extend(self._check_dependencies(self.root_files, all_numbers))
        
        for pieces in self.directories.values():
            issues.extend(self._check_dependencies(pieces, all_numbers))
        
        return issues


def safe_write_config(
    payload_discovery: PayloadDiscovery,
    config_path: str,
    backup: bool = True
) -> Path:
    """
    Safely write PayloadDiscovery configuration to JSON file.
    
    This function:
    1. Validates the configuration
    2. Creates a backup if file exists (optional)
    3. Writes atomically to prevent corruption
    
    Args:
        payload_discovery: The PayloadDiscovery instance to save
        config_path: Path where to save the JSON config
        backup: Whether to backup existing file (default: True)
        
    Returns:
        Path to the written config file
        
    Raises:
        ValueError: If configuration is invalid
    """
    config_path = Path(config_path)
    
    # Validate before writing
    issues = payload_discovery.validate_sequence()
    if issues:
        logger.warning(f"Configuration has validation issues: {issues}")
    
    # Backup existing file if requested
    if backup and config_path.exists():
        backup_path = config_path.with_suffix(f".backup_{os.getpid()}.json")
        config_path.rename(backup_path)
        logger.info(f"Created backup at {backup_path}")
    
    # Write atomically (write to temp, then rename)
    temp_path = config_path.with_suffix(f".tmp_{os.getpid()}.json")
    try:
        temp_path.write_text(payload_discovery.to_json())
        temp_path.rename(config_path)
        logger.info(f"Successfully wrote config to {config_path}")
    except Exception as e:
        # Clean up temp file if something went wrong
        if temp_path.exists():
            temp_path.unlink()
        raise e
    
    return config_path


def load_payload_discovery(config_path: str) -> PayloadDiscovery:
    """
    Convenience function to load a PayloadDiscovery from JSON.
    
    Args:
        config_path: Path to JSON configuration file
        
    Returns:
        PayloadDiscovery instance
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    return PayloadDiscovery.from_json(config_path)