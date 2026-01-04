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

# Import STARLOG for flight config registry access
from starlog_mcp.starlog import Starlog
from starlog_mcp.models import DebugDiaryEntry, StarlogPayloadDiscoveryConfig

app = FastMCP("Waypoint")
logger.info("Created Waypoint FastMCP application")

# No in-memory state - everything uses persistent JSON files


def _load_payload_discovery_from_state(starlog_path: str) -> Optional[PayloadDiscovery]:
    """Load PayloadDiscovery from config file based on JSON state."""
    if not starlog_path:
        return None
        
    project_name = Path(starlog_path).name
    state_data = _read_temp_json(project_name)
    
    if not state_data or state_data.get("status") == "END":
        return None
    
    # Get config path from state data
    config_path = state_data.get("config_path")
    if not config_path:
        # Fallback for old state format
        workflow = state_data.get("workflow", "starlog_flight")
        config_path = f"{starlog_path}/{workflow}.json"
    
    try:
        # Use the registry resolver to handle both file paths and registry keys
        resolved_path = _resolve_config_path_or_key(config_path)
        return load_payload_discovery(resolved_path)
    except Exception as e:
        logger.error(f"Failed to load PayloadDiscovery from {config_path}: {e}", exc_info=True)
        return None


def _get_active_journey_info(starlog_path: str) -> Optional[dict]:
    """Get info about active journey for a starlog path, if any."""
    if not starlog_path:
        return None
        
    project_name = Path(starlog_path).name
    state_data = _read_temp_json(project_name)
    
    if not state_data or state_data.get("status") == "END":
        return None
        
    # Return journey info for validation messages
    return {
        "domain": state_data.get("domain"),
        "version": state_data.get("version"), 
        "workflow": state_data.get("workflow"),
        "progress": f"{state_data.get('completed_count', 0)}/{state_data.get('total_waypoints', 0)}",
        "last_file": state_data.get("last_served_file"),
        "status": state_data.get("status")
    }


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


def _parse_temp_file(domain: str, version: str, project_name: str = None) -> List[str]:
    """Parse temp file to find completed pieces."""
    if project_name:
        temp_file = f"/tmp/waypoint_state_{project_name}.temp"
    else:
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
    project_name = Path(starlog_path).name if starlog_path else None
    return _parse_temp_file(domain, version, project_name)


def _write_to_temp_json(state_data: dict, project_name: str = None):
    """Write state data to temp JSON file for easy parsing."""
    if project_name:
        temp_file = f"/tmp/waypoint_state_{project_name}.json"
    else:
        temp_file = "/tmp/waypoint_state.json"
    try:
        with open(temp_file, 'w') as f:
            json.dump(state_data, f, indent=2)
        logger.debug(f"Wrote to temp JSON: {state_data}")
    except Exception as e:
        logger.error(f"Error writing temp JSON: {e}", exc_info=True)

def _read_temp_json(project_name: str = None) -> dict:
    """Read state data from temp JSON file."""
    if project_name:
        temp_file = f"/tmp/waypoint_state_{project_name}.json"
    else:
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
    project_name = Path(starlog_path).name if starlog_path else None
    state_data = _read_temp_json(project_name)
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


def _is_file_path(path_or_key: str) -> bool:
    """Check if string is a file path (contains '/') or registry key."""
    return "/" in path_or_key


def _create_flattened_pd(work_loop_subchain: str, registry_key: str, _visited: set = None) -> str:
    """Create flattened PayloadDiscovery combining STARLOG base with domain waypoints."""
    import tempfile
    
    # Resolve work_loop_subchain - could be file path OR another flight config
    try:
        if _is_file_path(work_loop_subchain):
            # Direct PayloadDiscovery file path
            with open(work_loop_subchain, 'r') as f:
                domain_pd_data = json.load(f)
            domain_waypoints = domain_pd_data.get('root_files', [])
        else:
            # Another flight config registry key - recursive resolution!
            resolved_subchain_path = _resolve_registry_key(work_loop_subchain, _visited)
            with open(resolved_subchain_path, 'r') as f:
                domain_pd_data = json.load(f)
            # Extract waypoints from the resolved flattened PD (skip base STARLOG steps)
            all_waypoints = domain_pd_data.get('root_files', [])
            # Skip first 4 STARLOG steps, take domain waypoints, skip final end step
            domain_waypoints = all_waypoints[4:-1] if len(all_waypoints) > 5 else []
    except Exception as e:
        logger.error(f"Failed to load/resolve subchain '{work_loop_subchain}': {e}")
        raise ValueError(f"Failed to load/resolve subchain '{work_loop_subchain}': {e}")
    
    # Create StarlogPayloadDiscoveryConfig instance
    starlog_pd = StarlogPayloadDiscoveryConfig()
    
    # Get the base structure as dict
    starlog_dict = starlog_pd.model_dump()
    
    # Get base STARLOG steps (first 4)
    base_steps = starlog_dict["root_files"][:4]
    
    # Modify Step 4 content based on whether domain waypoints exist
    if domain_waypoints:
        # With domain subchain: tell agent to continue navigation
        base_steps[3]["content"] += "\n\nNavigate to the next waypoint to continue with your domain-specific workflow."
    else:
        # Without domain subchain: tell agent when to end session
        base_steps[3]["content"] += "\n\nWhen your work is complete, navigate to the next waypoint to end the session."
    
    # Insert domain waypoints after step 4, renumbering
    flattened_files = base_steps[:]
    current_sequence = 5
    
    for waypoint in domain_waypoints:
        domain_step = waypoint.copy()
        domain_step["sequence_number"] = current_sequence
        # Ensure required fields for PayloadDiscovery compatibility
        if "piece_type" not in domain_step:
            domain_step["piece_type"] = "instruction"
        if "dependencies" not in domain_step:
            domain_step["dependencies"] = []
        flattened_files.append(domain_step)
        current_sequence += 1
    
    # Add end session step (from original or create new)
    if len(starlog_dict["root_files"]) > 4:
        # Use existing end session step, renumbered
        end_step = starlog_dict["root_files"][4].copy()
        end_step["sequence_number"] = current_sequence
        end_step["filename"] = f"{current_sequence:02d}_end_session.md"
        end_step["content"] = end_step["content"].replace("Step 5:", f"Step {current_sequence}:")
    else:
        # Create new end session step
        end_step = {
            "filename": f"{current_sequence:02d}_end_session.md",
            "title": "End STARLOG Session",
            "content": f"Step {current_sequence}: Complete session with summary\nUse: end_starlog(session_id, summary, path)\n\nComplete session with summary and outcomes. This formally closes the development session and saves all context.\n\nSTARLOG creates Captain's Log style XML output for AI context injection.",
            "sequence_number": current_sequence,
            "piece_type": "instruction",
            "dependencies": []
        }
    flattened_files.append(end_step)
    
    # Update the dict with flattened files
    starlog_dict["root_files"] = flattened_files
    
    # Write flattened PD to temp file
    temp_fd, temp_path = tempfile.mkstemp(suffix=f"_{registry_key}_flattened.json", prefix="waypoint_")
    try:
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(starlog_dict, f, indent=2)
        
        logger.info(f"Created flattened PD for '{registry_key}' at {temp_path}")
        return temp_path
        
    except Exception as e:
        os.unlink(temp_path)  # Clean up on error
        raise ValueError(f"Failed to create flattened PD: {e}")


def _resolve_registry_key(registry_key: str, _visited: set = None) -> str:
    """Resolve registry key to PayloadDiscovery file path by creating flattened PD on-the-fly."""
    if _visited is None:
        _visited = set()
    
    # Check for circular reference
    if registry_key in _visited:
        raise ValueError(f"Circular reference detected in flight configs: {' -> '.join(_visited)} -> {registry_key}")
    
    _visited.add(registry_key)
    
    starlog = Starlog()
    flight_data = starlog._get_flight_configs_registry_data()
    
    # Find config by name
    for config_id, config in flight_data.items():
        if config.get("name") == registry_key:
            work_loop_subchain = config.get("work_loop_subchain")
            if not work_loop_subchain:
                raise ValueError(f"Flight config '{registry_key}' has no work_loop_subchain")
            
            # Create and return flattened PD with visited tracking
            return _create_flattened_pd(work_loop_subchain, registry_key, _visited.copy())
    
    raise ValueError(f"Flight config '{registry_key}' not found in registry")


def _resolve_config_path_or_key(config_path_or_key: str) -> str:
    """
    Resolve config path or registry key to actual PayloadDiscovery file path.
    
    Args:
        config_path_or_key: Either a file path (contains '/') or registry key
        
    Returns:
        Path to PayloadDiscovery JSON file
        
    Raises:
        ValueError: If registry key not found or invalid
    """
    if _is_file_path(config_path_or_key):
        return config_path_or_key
    
    try:
        return _resolve_registry_key(config_path_or_key)
    except Exception as e:
        logger.error(f"Error resolving config key '{config_path_or_key}': {e}", exc_info=True)
        raise ValueError(f"Failed to resolve config key '{config_path_or_key}': {str(e)}")


@app.tool()
def start_waypoint_journey(config_path: str, starlog_path: str, notes: str = "") -> str:
    """Initialize a Waypoint learning journey."""
    logger.debug(f"start_waypoint_journey: config={config_path}, starlog={starlog_path}")
    
    # Check if journey already active for this starlog path
    active_journey = _get_active_journey_info(starlog_path)
    if active_journey:
        journey_info = f"Domain: {active_journey['domain']} | Progress: {active_journey['progress']} | Last: {active_journey['last_file']}"
        return f"❌ You can't start a new journey because you are on a journey. Either continue or abort it first. | {journey_info}"
    
    try:
        # Resolve registry key or file path to actual PayloadDiscovery file
        resolved_path = _resolve_config_path_or_key(config_path)
        pd = load_payload_discovery(resolved_path)
        # Store config_path in JSON state instead of in-memory dict
        config_filename = Path(config_path).stem
        
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
        project_name = Path(starlog_path).name
        state_data = _read_temp_json(project_name)
        if state_data.get("status") == "END":
            # Clear END status to allow restart
            temp_file = f"/tmp/waypoint_state_{project_name}.json"
            if os.path.exists(temp_file):
                os.remove(temp_file)
            logger.debug("Cleared END status, allowing restart")
        
        # Serve first waypoint
        first_sequence = _get_next_sequence_number(starlog_path, pd)
        if first_sequence is not None:
            piece = _get_piece_by_sequence(pd, first_sequence)
            if piece:
                _write_completion_entry(starlog_path, config_path, pd, piece, 1, notes)
                return piece.content
        
        return f"🚨 Error: No waypoints found in {pd.domain}"
        
    except Exception as e:
        logger.error(f"Error starting discovery: {e}", exc_info=True)
        return f"🚨 Error: {str(e)}"


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

def _write_completion_entry(starlog_path: str, config_path: str, pd: PayloadDiscovery, piece, completed_count: int, notes: str = ""):
    """Write completion entry to STARLOG diary and update JSON state."""
    total = _count_total_pieces(pd)
    step_info = f"Completed step {completed_count}/{total} - {piece.filename} served"
    
    # Always write JSON state for waypoint navigation
    project_name = Path(starlog_path).name if starlog_path else None
    config_filename = Path(config_path).stem if config_path else "workflow"
    state_data = {
        "domain": pd.domain,
        "version": pd.version,
        "config_path": config_path,
        "config_filename": config_filename,
        "last_served_sequence": piece.sequence_number,
        "total_waypoints": total,
        "last_served_file": piece.filename,
        "completed_count": completed_count,
        "status": "END" if completed_count >= total else "IN_PROGRESS"
    }
    _write_to_temp_json(state_data, project_name)
    
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
    pd = _load_payload_discovery_from_state(starlog_path)
    if not pd:
        return "🚨 No active discovery. Call start_waypoint_journey first."
    next_sequence = _get_next_sequence_number(starlog_path, pd)
    
    if next_sequence is None:
        _write_ended_entry(starlog_path, pd)
        return ""
    
    piece = _get_piece_by_sequence(pd, next_sequence)
    if not piece:
        return f"🚨 Error: Could not find piece for sequence {next_sequence}"
    
    # Need config_path - get from state or reconstruct
    project_name = Path(starlog_path).name if starlog_path else None
    state_data = _read_temp_json(project_name) 
    config_path = state_data.get("config_path") if state_data else None
    _write_completion_entry(starlog_path, config_path, pd, piece, piece.sequence_number)
    
    return piece.content

def _get_next_prompt_with_notes(starlog_path: str, notes: str = "") -> str:
    """Internal logic with notes support."""
    pd = _load_payload_discovery_from_state(starlog_path)
    if not pd:
        return "🚨 No active waypoint journey. Call start_waypoint_journey first."
    next_sequence = _get_next_sequence_number(starlog_path, pd)
    
    if next_sequence is None:
        _write_ended_entry(starlog_path, pd, notes)
        return ""
    
    piece = _get_piece_by_sequence(pd, next_sequence)
    if not piece:
        return f"🚨 Error: Could not find waypoint for sequence {next_sequence}"
    
    # Need config_path - get from state or reconstruct
    project_name = Path(starlog_path).name if starlog_path else None
    state_data = _read_temp_json(project_name)
    config_path = state_data.get("config_path") if state_data else None
    _write_completion_entry(starlog_path, config_path, pd, piece, piece.sequence_number, notes)

    autopoiesis_reminder = "\n\n---\n**Autopoiesis**: Consider what promises you need to make for this step. Use `be_autopoietic(\"promise\")` to commit to completing this step before moving to the next."

    return piece.content + autopoiesis_reminder

@app.tool()
def navigate_to_next_waypoint(starlog_path: str, notes: str = "") -> str:
    """Navigate to the next waypoint in the learning journey."""
    logger.debug(f"navigate_to_next_waypoint: starlog={starlog_path}")
    
    try:
        return _get_next_prompt_with_notes(starlog_path, notes)
    except Exception as e:
        logger.error(f"Error navigating to next waypoint: {e}", exc_info=True)
        return f"🚨 Error: {str(e)}"


@app.tool()
def get_waypoint_progress(starlog_path: str) -> str:
    """Get current progress through waypoint journey."""
    logger.debug(f"get_waypoint_progress: starlog={starlog_path}")
    
    try:
        pd = _load_payload_discovery_from_state(starlog_path)
        if not pd:
            return "No active waypoint journey."
        
        # Get progress from JSON state directly
        project_name = Path(starlog_path).name
        state_data = _read_temp_json(project_name)
        if state_data:
            completed_count = state_data.get('completed_count', 0)
        else:
            completed_count = 0
        
        total = _count_total_pieces(pd)
        percentage = (completed_count / total) * 100 if total > 0 else 0
        
        return (
            f"🛸 Waypoint Journey: {pd.domain} {pd.version}\n"
            f"⭐ Sectors Cleared: {completed_count}/{total} waypoints ({percentage:.1f}% complete)\n"
            f"🌌 Current Sector: {pd.entry_point}"
        )
        
    except Exception as e:
        logger.error(f"Error getting waypoint progress: {e}", exc_info=True)
        return f"🚨 Error: {str(e)}"


@app.tool()
def abort_waypoint_journey(starlog_path: str, notes: str = "") -> str:
    """Abort active waypoint journey and clear state."""
    logger.debug(f"abort_waypoint_journey: starlog={starlog_path}")
    
    try:
        # Check if there's an active journey
        active_journey = _get_active_journey_info(starlog_path)
        if not active_journey:
            return "🪂 No active waypoint journey to abort."
        
        # Clear state files
        project_name = Path(starlog_path).name
        temp_json = f"/tmp/waypoint_state_{project_name}.json"
        temp_file = f"/tmp/waypoint_state_{project_name}.temp"
        
        if os.path.exists(temp_json):
            os.remove(temp_json)
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        # Get domain/version from active journey info for logging
        domain = active_journey.get('domain', 'unknown')
        version = active_journey.get('version', 'unknown')
        
        # Write abort log to starlog if available
        _write_waypoint_log(
                starlog_path,
                type('pd', (), {'domain': domain, 'version': version})(),
                "ABORT",
                step_info=f"Journey aborted - Progress: {active_journey['progress']}",
                notes=notes or "Journey manually aborted",
                filename="abort"
            )
        
        return f"🪂 Aborted waypoint journey: {active_journey['domain']} {active_journey['version']}"
        
    except Exception as e:
        logger.error(f"Error aborting waypoint journey: {e}", exc_info=True)
        return f"🪂 Error: {str(e)}"


@app.tool()
def get_current_step_content(starlog_path: str) -> str:
    """
    Get current waypoint step content WITHOUT advancing to next step.

    This is used by Super-Ralph Stop hook to inject current step context
    without changing journey progress. Safe to call repeatedly.

    Args:
        starlog_path: STARLOG project path with active waypoint journey

    Returns:
        Current step content, or error message if no active journey
    """
    logger.debug(f"get_current_step_content: starlog={starlog_path}")

    try:
        pd = _load_payload_discovery_from_state(starlog_path)
        if not pd:
            return "No active waypoint journey."

        # Get current sequence from JSON state
        project_name = Path(starlog_path).name if starlog_path else None
        state_data = _read_temp_json(project_name)

        if not state_data:
            return "No waypoint state found."

        last_served = state_data.get("last_served_sequence")
        if last_served is None:
            return "No step has been served yet."

        # Get the piece for the last served sequence (current step)
        piece = _get_piece_by_sequence(pd, last_served)
        if not piece:
            return f"Could not find content for step {last_served}"

        # Return content with metadata
        total = state_data.get("total_waypoints", _count_total_pieces(pd))
        completed = state_data.get("completed_count", last_served)

        return (
            f"📋 Step {completed}/{total}: {piece.filename}\n"
            f"---\n"
            f"{piece.content}"
        )

    except Exception as e:
        logger.error(f"Error getting current step content: {e}", exc_info=True)
        return f"Error: {str(e)}"


@app.tool()
def reset_waypoint_journey(starlog_path: str, notes: str = "") -> str:
    """Reset waypoint journey progress to beginning."""
    logger.debug(f"reset_waypoint_journey: starlog={starlog_path}")
    
    try:
        # Check if there's an active journey first
        active_journey = _get_active_journey_info(starlog_path)
        if not active_journey:
            return "🌌 No active waypoint journey to reset."
            
        pd = _load_payload_discovery_from_state(starlog_path)
        if not pd:
            return "🌌 No active waypoint journey to reset."
        
        _write_waypoint_log(
            starlog_path,
            pd,
            "RESET",
            step_info="Navigation sequence restarted",
            notes=notes or "Plotting new course from beginning",
            filename="reset"
        )
        
        return f"🔄 Waypoint journey reset: {pd.domain} {pd.version}"
        
    except Exception as e:
        logger.error(f"Error resetting waypoint journey: {e}", exc_info=True)
        return f"🚨 Error: {str(e)}"


def main():
    """Main entry point for console script."""
    logger.info("Starting PayloadDiscovery MCP server")
    app.run()


if __name__ == "__main__":
    main()