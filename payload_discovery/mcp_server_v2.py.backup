"""
Waypoint MCP Server - Agent navigation system for structured learning journeys.

Agents traverse waypoints in a curriculum, logging their progress like a starship captain.
"""

import logging
import json
import os
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    logger.error("FastMCP not available - install mcp package", exc_info=True)
    raise

from .core import PayloadDiscovery, load_payload_discovery

# No STARLOG imports needed - using direct registry access

app = FastMCP("Waypoint")
logger.info("Created Waypoint FastMCP application")

_active_discoveries: Dict[str, PayloadDiscovery] = {}


def _get_waypoint_tag(domain: str, version: str, filename: str = "workflow") -> str:
    """Get the waypoint tag for Captain's Log entries."""
    return f"@waypoint:{domain}:{version}({filename})"

def _format_captains_log(domain: str, version: str, status: str, step_info: str = "", notes: str = "", filename: str = "workflow") -> str:
    """Format entry as waypoint log."""
    waypoint_tag = _get_waypoint_tag(domain, version, filename)
    
    log_entry = f"🧭 {waypoint_tag} {status}"
    
    if step_info:
        log_entry += f" {step_info}"
    
    if notes:
        log_entry += f" - {notes}"
    
    return log_entry


def _extract_completed_filename(content: str, tag: str) -> Optional[str]:
    """Extract filename from diary entry content."""
    if '🧭 @waypoint:' not in content:
        return None
    
    try:
        # Extract filename from 🧭 @waypoint:domain:version(filename.md) format
        waypoint_start = content.find('🧭 @waypoint:')
        waypoint_part = content[waypoint_start:]
        paren_start = waypoint_part.find('(')
        paren_end = waypoint_part.find(')')
        
        if paren_start == -1 or paren_end == -1:
            return None
            
        filename = waypoint_part[paren_start + 1:paren_end]
        return filename if filename else None
        
    except Exception as e:
        logger.debug(f"Error extracting filename: {e}", exc_info=True)
        return None


def _extract_completed_filenames_from_registry_data(diary_data: Dict, tag: str) -> List[str]:
    """Extract completed filenames from diary registry data."""
    completed = []
    for entry_id, entry_data in diary_data.items():
        if isinstance(entry_data, dict):
            content = entry_data.get('content', '')
            filename = _extract_completed_filename(content, tag)
            if filename:
                completed.append(filename)
    return completed


def _parse_temp_file(domain: str, version: str) -> List[str]:
    """Parse temp file to find completed pieces."""
    temp_file = "/tmp/waypoint_state.temp"
    try:
        if not os.path.exists(temp_file):
            return []
        
        with open(temp_file, 'r') as f:
            content = f.read().strip()
        
        # Extract step count from "Completed step X/Y" format
        import re
        step_match = re.search(r"Completed step (\d+)/(\d+)", content)
        if step_match:
            completed_step = int(step_match.group(1))
            # Return a list with the right number of dummy filenames to get the count right
            return [f"step_{i}.md" for i in range(1, completed_step + 1)]
        
        # Fallback to old filename extraction if no step count found
        filename = _extract_completed_filename(content, "")
        return [filename] if filename else []
        
    except Exception as e:
        logger.error(f"Error parsing temp file: {e}", exc_info=True)
        return []


def _parse_diary_entries(starlog_path: str, domain: str, version: str) -> List[str]:
    """Parse temp file to find completed pieces."""
    # Always use temp file for waypoint state tracking
    return _parse_temp_file(domain, version)


def _write_to_temp_json(state_data: dict):
    """Write state data to temp JSON file for easy parsing."""
    temp_file = "/tmp/waypoint_state.json"
    try:
        with open(temp_file, 'w') as f:
            json.dump(state_data, f, indent=2)
        logger.debug(f"Wrote to temp JSON: {state_data}")
    except Exception as e:
        logger.error(f"Error writing temp JSON: {e}", exc_info=True)

def _read_temp_json() -> dict:
    """Read state data from temp JSON file."""
    temp_file = "/tmp/waypoint_state.json"
    try:
        if not os.path.exists(temp_file):
            return {}
        with open(temp_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading temp JSON: {e}", exc_info=True)
        return {}

def _write_diary_entry(starlog_path: str, content: str, insights: Optional[str] = None):
    """Write an entry to the starlog debug diary by directly modifying registry JSON."""
    if not starlog_path:
        return
        
    try:
        # Get HEAVEN_DATA_DIR and reconstruct registry path
        heaven_data_dir = os.environ.get('HEAVEN_DATA_DIR')
        if not heaven_data_dir:
            logger.warning("HEAVEN_DATA_DIR not set, cannot write to starlog debug diary")
            return
            
        # Extract project name from starlog_path
        project_name = Path(starlog_path).name
        registry_path = f"{heaven_data_dir}/registry/{project_name}_debug_diary_registry.json"
        
        # Read existing registry
        registry_data = {}
        if os.path.exists(registry_path):
            with open(registry_path, 'r') as f:
                registry_data = json.load(f)
        
        # Create entry mimicking DebugDiaryEntry structure
        entry_id = f"diary_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": entry_id,
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "insights": insights,
            "in_file": None,
            "bug_report": False,
            "bug_fix": False,
            "issue_id": None,
            "from_github": False
        }
        
        # Add entry to registry
        registry_data[entry_id] = entry
        
        # Write back to registry
        with open(registry_path, 'w') as f:
            json.dump(registry_data, f, indent=2)
            
        logger.debug(f"Wrote diary entry directly to registry: {content[:50]}...")
        return
        
    except Exception as e:
        logger.error(f"Error writing STARLOG diary entry directly: {e}", exc_info=True)


def _map_filenames_to_sequence_numbers(pd: PayloadDiscovery, completed_filenames: List[str]) -> List[int]:
    """Map completed filenames back to sequence numbers."""
    completed_numbers = []
    
    for piece in pd.root_files:
        if piece.filename in completed_filenames:
            completed_numbers.append(piece.sequence_number)
    
    for pieces in pd.directories.values():
        for piece in pieces:
            if piece.filename in completed_filenames:
                completed_numbers.append(piece.sequence_number)
    
    return completed_numbers


def _count_total_pieces(pd: PayloadDiscovery) -> int:
    """Count total pieces in PayloadDiscovery."""
    total = len(pd.root_files)
    for pieces in pd.directories.values():
        total += len(pieces)
    return total


def _get_next_sequence_number(starlog_path: str, pd: PayloadDiscovery) -> Optional[int]:
    """Find the next sequence number to serve based on JSON state."""
    # Try JSON state first
    state_data = _read_temp_json()
    if state_data and "last_served_sequence" in state_data:
        last_served = state_data["last_served_sequence"]
        
        # Find all pieces in sequence order
        all_pieces = []
        for piece in pd.root_files:
            all_pieces.append(piece)
        for pieces in pd.directories.values():
            all_pieces.extend(pieces)
        
        # Sort by sequence number
        all_pieces.sort(key=lambda p: p.sequence_number)
        
        # Find next sequence after last served
        for piece in all_pieces:
            if piece.sequence_number > last_served:
                return piece.sequence_number
        
        return None  # All complete
    
    # Fallback to diary parsing if no JSON state
    completed_filenames = _parse_diary_entries(starlog_path, pd.domain, pd.version)
    completed_numbers = set(_map_filenames_to_sequence_numbers(pd, completed_filenames))
    
    # Find all pieces in sequence order
    all_pieces = []
    for piece in pd.root_files:
        all_pieces.append(piece)
    for pieces in pd.directories.values():
        all_pieces.extend(pieces)
    
    # Sort by sequence number
    all_pieces.sort(key=lambda p: p.sequence_number)
    
    # Find first uncompleted piece
    for piece in all_pieces:
        if piece.sequence_number not in completed_numbers:
            return piece.sequence_number
    
    return None  # All complete


def _find_piece_by_sequence(pd: PayloadDiscovery, sequence_num: int) -> Optional[str]:
    """Find piece filename by sequence number."""
    for p in pd.root_files:
        if p.sequence_number == sequence_num:
            return p.filename
    
    for pieces in pd.directories.values():
        for p in pieces:
            if p.sequence_number == sequence_num:
                return p.filename
    
    return None


def _get_piece_by_sequence(pd: PayloadDiscovery, sequence_num: int):
    """Get piece object by sequence number."""
    for piece in pd.root_files:
        if piece.sequence_number == sequence_num:
            return piece
    
    for pieces in pd.directories.values():
        for piece in pieces:
            if piece.sequence_number == sequence_num:
                return piece
    
    return None


@app.tool()
def start_waypoint_journey(config_path: str, starlog_path: str, notes: str = "") -> str:
    """Initialize a Waypoint learning journey."""
    logger.debug(f"start_waypoint_journey: config={config_path}, starlog={starlog_path}")
    
    try:
        pd = load_payload_discovery(config_path)
        _active_discoveries[starlog_path] = pd
        
        total_pieces = _count_total_pieces(pd)
        config_filename = Path(config_path).stem
        
        # Write START message
        _write_waypoint_log(
            starlog_path,
            pd,
            "START",
            step_info=f"Journey initialized with {total_pieces} waypoints",
            notes=notes or "Beginning navigation sequence",
            filename=config_filename
        )
        
        # Check if previous journey ended, allow restart
        state_data = _read_temp_json()
        if state_data.get("status") == "END":
            # Clear END status to allow restart
            temp_file = "/tmp/waypoint_state.json"
            if os.path.exists(temp_file):
                os.remove(temp_file)
            logger.debug("Cleared END status, allowing restart")
        
        # Serve first waypoint
        first_sequence = _get_next_sequence_number(starlog_path, pd)
        if first_sequence is not None:
            piece = _get_piece_by_sequence(pd, first_sequence)
            if piece:
                _write_completion_entry(starlog_path, pd, piece, 1, notes, config_filename)
                return piece.content
        
        return f"❌ Error: No waypoints found in {pd.domain}"
        
    except Exception as e:
        logger.error(f"Error starting discovery: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


def _write_waypoint_log(starlog_path: str, pd: PayloadDiscovery, status: str, step_info: str = "", notes: str = "", filename: str = "workflow"):
    """Write waypoint log entry to STARLOG diary."""
    log_entry = _format_captains_log(
        domain=pd.domain,
        version=pd.version,
        status=status,
        step_info=step_info,
        notes=notes,
        filename=filename
    )
    _write_diary_entry(starlog_path, log_entry)

def _write_completion_entry(starlog_path: str, pd: PayloadDiscovery, piece, completed_count: int, notes: str = "", config_filename: str = "workflow"):
    """Write completion entry to STARLOG diary and update JSON state."""
    total = _count_total_pieces(pd)
    step_info = f"Completed step {completed_count}/{total} - {piece.filename} served"
    
    # Always write JSON state for waypoint navigation
    state_data = {
        "domain": pd.domain,
        "version": pd.version,
        "workflow": config_filename,
        "last_served_sequence": piece.sequence_number,
        "total_waypoints": total,
        "last_served_file": piece.filename,
        "completed_count": completed_count,
        "status": "END" if completed_count >= total else "IN_PROGRESS"
    }
    _write_to_temp_json(state_data)
    
    # Additionally write to starlog debug diary if available
    if starlog_path:
        _write_waypoint_log(starlog_path, pd, step_info, notes=notes, filename=config_filename)

def _write_ended_entry(starlog_path: str, pd: PayloadDiscovery, notes: str = ""):
    """Write ENDED entry to STARLOG diary."""
    _write_waypoint_log(
        starlog_path, 
        pd, 
        "END", 
        step_info="All waypoints traversed successfully", 
        notes=notes or "Mission accomplished",
        filename="completion"
    )

def _get_next_prompt_internal(starlog_path: str) -> str:
    """Internal logic: find last completed step, serve next step, write completion."""
    if starlog_path not in _active_discoveries:
        return "❌ No active discovery. Call start_payload_discovery first."
    
    pd = _active_discoveries[starlog_path]
    next_sequence = _get_next_sequence_number(starlog_path, pd)
    
    if next_sequence is None:
        _write_ended_entry(starlog_path, pd)
        return ""
    
    piece = _get_piece_by_sequence(pd, next_sequence)
    if not piece:
        return f"❌ Error: Could not find piece for sequence {next_sequence}"
    
    _write_completion_entry(starlog_path, pd, piece, piece.sequence_number)
    
    return piece.content

def _get_next_prompt_with_notes(starlog_path: str, notes: str = "") -> str:
    """Internal logic with notes support."""
    if starlog_path not in _active_discoveries:
        return "❌ No active waypoint journey. Call start_waypoint_journey first."
    
    pd = _active_discoveries[starlog_path]
    next_sequence = _get_next_sequence_number(starlog_path, pd)
    
    if next_sequence is None:
        _write_ended_entry(starlog_path, pd, notes)
        return ""
    
    piece = _get_piece_by_sequence(pd, next_sequence)
    if not piece:
        return f"❌ Error: Could not find waypoint for sequence {next_sequence}"
    
    _write_completion_entry(starlog_path, pd, piece, piece.sequence_number, notes)
    
    return piece.content

@app.tool()
def navigate_to_next_waypoint(starlog_path: str, notes: str = "") -> str:
    """Navigate to the next waypoint in the learning journey."""
    logger.debug(f"navigate_to_next_waypoint: starlog={starlog_path}")
    
    try:
        return _get_next_prompt_with_notes(starlog_path, notes)
    except Exception as e:
        logger.error(f"Error navigating to next waypoint: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@app.tool()
def get_waypoint_progress(starlog_path: str) -> str:
    """Get current progress through waypoint journey."""
    logger.debug(f"get_waypoint_progress: starlog={starlog_path}")
    
    try:
        if starlog_path not in _active_discoveries:
            return "No active waypoint journey."
        
        pd = _active_discoveries[starlog_path]
        completed_filenames = _parse_diary_entries(starlog_path, pd.domain, pd.version)
        completed_count = len(completed_filenames)
        total = _count_total_pieces(pd)
        percentage = (completed_count / total) * 100 if total > 0 else 0
        
        return (
            f"Waypoint Journey: {pd.domain} {pd.version}\n"
            f"Navigation Progress: {completed_count}/{total} waypoints ({percentage:.1f}% complete)\n"
            f"Current Sector: {pd.entry_point}"
        )
        
    except Exception as e:
        logger.error(f"Error getting waypoint progress: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@app.tool()
def reset_waypoint_journey(starlog_path: str, notes: str = "") -> str:
    """Reset waypoint journey progress to beginning."""
    logger.debug(f"reset_waypoint_journey: starlog={starlog_path}")
    
    try:
        if starlog_path not in _active_discoveries:
            return "No active waypoint journey to reset."
        
        pd = _active_discoveries[starlog_path]
        
        _write_waypoint_log(
            starlog_path,
            pd,
            "RESET",
            step_info="Navigation sequence restarted",
            notes=notes or "Plotting new course from beginning",
            filename="reset"
        )
        
        return f"✅ Waypoint journey reset: {pd.domain} {pd.version}"
        
    except Exception as e:
        logger.error(f"Error resetting waypoint journey: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


def main():
    """Main entry point for console script."""
    logger.info("Starting PayloadDiscovery MCP server")
    app.run()


if __name__ == "__main__":
    main()