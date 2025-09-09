"""
PayloadDiscovery MCP Tool - Self-prompting agent curriculum system.

This MCP wraps the PayloadDiscovery/HEAVEN PIS integration to enable agents
to autonomously consume numbered instruction sequences while tracking progress
in STARLOG.

## How It Works:

1. Agent calls `start_payload_discovery(config_path, starlog_path)`
   - Loads PayloadDiscovery from JSON
   - Renders to filesystem 
   - Initializes STARLOG session
   - Writes first debug diary entry

2. Agent calls `get_next_discovery_prompt(starlog_path)` in a loop
   - Reads debug diary to find last completed piece (stateless!)
   - Reconstructs state from diary entries (no separate state machine needed)
   - Returns next prompt from sequence
   - Auto-updates debug diary with new piece completed

3. Agent continues until `has_more_prompts(starlog_path)` returns False
   - Checks debug diary for completion
   - Returns progress summary

## The Clever Trick:

Instead of maintaining a separate state machine, we use STARLOG's debug diary
as the source of truth. Each call:
1. Reads all PayloadDiscovery entries from debug diary
2. Calculates which pieces have been completed
3. Determines next piece to serve
4. Updates diary and returns prompt

This makes the system:
- Stateless (state lives in STARLOG)
- Resumable (just pass the same starlog_path)
- Auditable (complete history in debug diary)
- Simple (no state synchronization issues)

## Debug Diary Entry Format:

```
[PayloadDiscovery:{domain}:{version}] Started discovery system
[PayloadDiscovery:{domain}:{version}] Completed: 00_Overview.md (1/32 pieces, 3.1%)
[PayloadDiscovery:{domain}:{version}] Completed: 01_Getting_Started.md (2/32 pieces, 6.2%)
...
[PayloadDiscovery:{domain}:{version}] Completed: All pieces processed (32/32 pieces, 100%)
```

## MCP Tool Interface:

```python
@mcp_tool
def start_payload_discovery(
    config_path: str,      # Path to PayloadDiscovery JSON
    starlog_path: str,     # REQUIRED: Active STARLOG project path
    render_path: str = "/tmp"  # Where to render filesystem
) -> str:
    '''Initialize a PayloadDiscovery learning session.'''
    pass

@mcp_tool
def get_next_discovery_prompt(
    starlog_path: str      # REQUIRED: To read/write progress
) -> str:
    '''Get next prompt in sequence. Returns empty string if complete.'''
    pass

@mcp_tool  
def get_discovery_progress(
    starlog_path: str      # REQUIRED: To read progress
) -> str:
    '''Get current progress through discovery system.'''
    pass

@mcp_tool
def reset_discovery(
    starlog_path: str      # REQUIRED: To clear progress
) -> str:
    '''Reset to beginning of discovery sequence.'''
    pass
```

## Implementation Strategy:

1. **State Reconstruction from Debug Diary**:
   - Parse all entries with pattern `[PayloadDiscovery:*]`
   - Extract completed pieces from "Completed: {filename}" entries
   - Rebuild DiscoveryReceipt from this data
   - No database, no state file, just STARLOG!

2. **Idempotent Operations**:
   - Multiple calls to get_next with same state = same result
   - Can safely retry on failures
   - Progress only advances when diary is updated

3. **Domain Tracking**:
   - Support multiple PayloadDiscovery systems in same STARLOG
   - Use domain:version prefix to separate them
   - Agent can work through multiple curricula

## Usage Example:

```python
# Agent's self-prompting loop (in agent code):
start_payload_discovery(
    "3pass_system.json",
    "/tmp/agent_learning_session"
)

while True:
    prompt = get_next_discovery_prompt("/tmp/agent_learning_session")
    if not prompt:
        break
    
    # Process the instruction
    result = process_instruction(prompt)
    
    # Optionally add agent's own insights to diary
    update_debug_diary(
        "/tmp/agent_learning_session",
        f"My understanding: {result}"
    )

progress = get_discovery_progress("/tmp/agent_learning_session")
logger.info(f"Learning complete! {progress}")
```

## Benefits of This Approach:

1. **No State Machine Complexity**: State lives in STARLOG debug diary
2. **Perfect Audit Trail**: Every step is logged with timestamp
3. **Resume Anywhere**: Just need the starlog_path to continue
4. **Multiple Agents**: Can share same discovery progress
5. **Debugging Paradise**: Can see exactly what agent learned when
6. **Meta-Learning**: Can analyze patterns across many discovery sessions

## TODO: Implementation

- [ ] Create FastMCP server wrapper
- [ ] Implement state reconstruction from debug diary
- [ ] Add domain:version namespacing for multiple discoveries
- [ ] Create helper to parse PayloadDiscovery diary entries
- [ ] Add progress calculation from diary
- [ ] Test with 3pass_autonomous_research_system example
"""

# Implementation will go here after design approval