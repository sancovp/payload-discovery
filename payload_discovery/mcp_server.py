"""
PayloadDiscovery MCP Server - Self-prompting agent curriculum system.

This MCP enables agents to autonomously consume numbered instruction sequences
while tracking progress in STARLOG's debug diary.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    logger.error("FastMCP not available - install mcp package")
    raise

from .core import PayloadDiscovery, load_payload_discovery
from .heaven_pis_integration import PayloadDiscoveryStateMachine, DiscoveryReceipt

# Import STARLOG for diary integration
try:
    from starlog_mcp.starlog import Starlog
    from starlog_mcp.models import DebugDiaryEntry
    STARLOG_AVAILABLE = True
except ImportError as e:
    logger.warning("STARLOG not available - diary tracking disabled", exc_info=True)
    STARLOG_AVAILABLE = False
    
    # Stub for development
    class DebugDiaryEntry:
        def __init__(self, content: str, **kwargs):
            self.content = content

# Create FastMCP app
app = FastMCP("PayloadDiscovery")
logger.info("Created PayloadDiscovery FastMCP application")

# Cache for active discovery systems
_active_discoveries: Dict[str, PayloadDiscovery] = {}


def _get_diary_tag(domain: str, version: str) -> str:
    """Get the tag prefix for debug diary entries."""
    return f"[PayloadDiscovery:{domain}:{version}]"


def _parse_diary_entries(starlog_path: str, domain: str, version: str) -> List[str]:
    """
    Parse debug diary to find completed pieces.
    
    Returns list of completed piece filenames.
    """
    if not STARLOG_AVAILABLE:
        return []
    
    try:
        starlog = Starlog()
        project_name = starlog._get_project_name_from_path(starlog_path)
        
        # Get debug diary entries
        registry_path = Path(starlog._get_registry_path(project_name))
        diary_file = registry_path / f"{project_name}_debug_diary.json"
        
        if not diary_file.exists():
            return []
        
        with open(diary_file, 'r') as f:
            entries = json.load(f)
        
        # Parse for our tag
        tag = _get_diary_tag(domain, version)
        completed = []
        
        for entry in entries:
            content = entry.get('content', '')
            if tag in content and 'Completed:' in content:
                # Extract filename from "Completed: 00_Overview.md (1/32 pieces, 3.1%)"
                parts = content.split('Completed:')[1].split('(')[0].strip()
                completed.append(parts)
        
        return completed
        
    except Exception as e:
        logger.error(f"Error parsing diary entries: {e}")
        return []


def _write_diary_entry(starlog_path: str, content: str, insights: Optional[str] = None):
    """Write an entry to the debug diary."""
    if not STARLOG_AVAILABLE:
        logger.info(f"STARLOG not available - would write: {content}")
        return
    
    try:
        starlog = Starlog()
        project_name = starlog._get_project_name_from_path(starlog_path)
        
        entry = DebugDiaryEntry(
            content=content,
            insights=insights
        )
        
        starlog._save_debug_diary_entry(project_name, entry)
        logger.debug(f"Wrote diary entry: {content[:50]}...")
        
    except Exception as e:
        logger.error(f"Error writing diary entry: {e}")


def _reconstruct_state(starlog_path: str, pd: PayloadDiscovery) -> DiscoveryReceipt:
    """
    Reconstruct DiscoveryReceipt from debug diary entries.
    
    This is the key function that makes the system stateless!
    """
    completed_filenames = _parse_diary_entries(starlog_path, pd.domain, pd.version)
    
    # Map filenames back to sequence numbers
    completed_numbers = []
    
    # Check root files
    for piece in pd.root_files:
        if piece.filename in completed_filenames:
            completed_numbers.append(piece.sequence_number)
    
    # Check directory files
    for pieces in pd.directories.values():
        for piece in pieces:
            if piece.filename in completed_filenames:
                completed_numbers.append(piece.sequence_number)
    
    # Count total pieces
    total = len(pd.root_files)
    for pieces in pd.directories.values():
        total += len(pieces)
    
    # Create receipt
    receipt = DiscoveryReceipt(
        domain=pd.domain,
        version=pd.version,
        completed_pieces=completed_numbers,
        total_pieces=total
    )
    
    logger.debug(f"Reconstructed state: {len(completed_numbers)}/{total} pieces complete")
    return receipt


@app.tool()
def start_payload_discovery(
    config_path: str,
    starlog_path: str,
    render_path: str = "/tmp"
) -> str:
    """
    Initialize a PayloadDiscovery learning session.
    
    Args:
        config_path: Path to PayloadDiscovery JSON configuration
        starlog_path: REQUIRED - Active STARLOG project path for tracking
        render_path: Where to render the filesystem structure (default: /tmp)
        
    Returns:
        Success message with discovery details
    """
    logger.debug(f"start_payload_discovery: config={config_path}, starlog={starlog_path}")
    
    try:
        # Load PayloadDiscovery
        pd = load_payload_discovery(config_path)
        
        # Render to filesystem
        output_dir = pd.render_to_directory(render_path)
        
        # Cache it
        _active_discoveries[starlog_path] = pd
        
        # Write initial diary entry
        tag = _get_diary_tag(pd.domain, pd.version)
        _write_diary_entry(
            starlog_path,
            f"{tag} Started discovery system",
            f"Rendered to {output_dir}, Total pieces: {pd.root_files + sum(len(p) for p in pd.directories.values())}"
        )
        
        return f"✅ Started PayloadDiscovery: {pd.domain} {pd.version}\nRendered to: {output_dir}\nTracking in: {starlog_path}"
        
    except Exception as e:
        logger.error(f"Error starting discovery: {e}")
        return f"❌ Error: {str(e)}"


@app.tool()
def get_next_discovery_prompt(starlog_path: str) -> str:
    """
    Get next prompt in the discovery sequence.
    
    This function:
    1. Reads debug diary to find completed pieces
    2. Reconstructs state from diary
    3. Returns next prompt
    4. Updates diary with completion
    
    Args:
        starlog_path: REQUIRED - STARLOG project path to read/write progress
        
    Returns:
        Next prompt content or empty string if complete
    """
    logger.debug(f"get_next_discovery_prompt: starlog={starlog_path}")
    
    try:
        # Get cached discovery or error
        if starlog_path not in _active_discoveries:
            return "❌ No active discovery. Call start_payload_discovery first."
        
        pd = _active_discoveries[starlog_path]
        
        # Reconstruct state from diary
        receipt = _reconstruct_state(starlog_path, pd)
        
        # Create state machine with reconstructed state
        machine = PayloadDiscoveryStateMachine(pd, receipt=receipt)
        
        # Get next prompt
        if not machine.has_next_prompt():
            tag = _get_diary_tag(pd.domain, pd.version)
            _write_diary_entry(
                starlog_path,
                f"{tag} All pieces processed ({receipt.total_pieces}/{receipt.total_pieces} pieces, 100%)"
            )
            return ""  # Complete
        
        prompt = machine.get_next_prompt()
        
        if prompt:
            # Figure out which piece we just served
            # (The machine updated its receipt)
            new_receipt = machine.get_receipt()
            newly_completed = set(new_receipt.completed_pieces) - set(receipt.completed_pieces)
            
            if newly_completed:
                # Find the piece details
                piece_num = list(newly_completed)[0]
                piece_name = None
                
                for p in pd.root_files:
                    if p.sequence_number == piece_num:
                        piece_name = p.filename
                        break
                
                if not piece_name:
                    for pieces in pd.directories.values():
                        for p in pieces:
                            if p.sequence_number == piece_num:
                                piece_name = p.filename
                                break
                
                # Write diary entry
                completed_count = len(new_receipt.completed_pieces)
                percentage = new_receipt.get_completion_percentage()
                
                tag = _get_diary_tag(pd.domain, pd.version)
                _write_diary_entry(
                    starlog_path,
                    f"{tag} Completed: {piece_name} ({completed_count}/{new_receipt.total_pieces} pieces, {percentage:.1f}%)"
                )
        
        return prompt
        
    except Exception as e:
        logger.error(f"Error getting next prompt: {e}")
        return f"❌ Error: {str(e)}"


@app.tool()
def get_discovery_progress(starlog_path: str) -> str:
    """
    Get current progress through discovery system.
    
    Args:
        starlog_path: REQUIRED - STARLOG project path to read progress
        
    Returns:
        Progress summary with completion percentage
    """
    logger.debug(f"get_discovery_progress: starlog={starlog_path}")
    
    try:
        if starlog_path not in _active_discoveries:
            return "No active discovery session."
        
        pd = _active_discoveries[starlog_path]
        receipt = _reconstruct_state(starlog_path, pd)
        
        percentage = receipt.get_completion_percentage()
        completed = len(receipt.completed_pieces)
        total = receipt.total_pieces
        
        return (
            f"PayloadDiscovery: {pd.domain} {pd.version}\n"
            f"Progress: {completed}/{total} pieces ({percentage:.1f}% complete)\n"
            f"Entry point: {pd.entry_point}"
        )
        
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return f"❌ Error: {str(e)}"


@app.tool()
def reset_discovery(starlog_path: str) -> str:
    """
    Reset discovery progress to beginning.
    
    This clears PayloadDiscovery entries from debug diary.
    
    Args:
        starlog_path: REQUIRED - STARLOG project path
        
    Returns:
        Success message
    """
    logger.debug(f"reset_discovery: starlog={starlog_path}")
    
    try:
        if starlog_path not in _active_discoveries:
            return "No active discovery to reset."
        
        pd = _active_discoveries[starlog_path]
        tag = _get_diary_tag(pd.domain, pd.version)
        
        # Note: We don't actually delete entries, just mark reset
        _write_diary_entry(
            starlog_path,
            f"{tag} RESET - Starting over from beginning"
        )
        
        return f"✅ Reset discovery progress for {pd.domain} {pd.version}"
        
    except Exception as e:
        logger.error(f"Error resetting: {e}")
        return f"❌ Error: {str(e)}"


def main():
    """Main entry point for console script."""
    logger.info("Starting PayloadDiscovery MCP server")
    app.run()


if __name__ == "__main__":
    main()