# Payload Discovery

A systematic agent learning framework that creates numbered instruction sequences and tracks progress through STARLOG integration.

## Overview

Payload Discovery solves the problem of systematic agent learning by creating structured, sequential instruction files that agents consume in order. The system is stateless - all progress is tracked through STARLOG's debug diary, enabling agents to resume learning sessions seamlessly.

This package provides both a **core library** for creating instruction sequences and an **MCP server** for agent consumption.

## Core Library Features

- 📚 **PayloadDiscovery Models**: Pydantic models for creating structured instruction sequences
- 🏗 **Filesystem Rendering**: Generate numbered instruction files from JSON configuration
- ✅ **Validation System**: Dependency checking and sequence validation
- 💾 **JSON Serialization**: Export/import instruction sequences as JSON

## MCP Server Features  

- 🛠 **Waypoint Navigation**: MCP tools for agents to traverse instruction sequences
- 📊 **STARLOG Integration**: Progress tracking through debug diary (stateless)
- 🔄 **Resume Capability**: Agents can restart and continue from last completed piece
- 🎯 **Agent-Focused**: Designed for autonomous agent consumption

## Quick Start

### Installation

[Installation instructions pending PyPI publication]

### Basic Usage

```python
from payload_discovery import PayloadDiscovery, PayloadDiscoveryPiece

# Create individual instruction pieces
piece1 = PayloadDiscoveryPiece(
    number=1,
    instruction="Analyze the codebase structure",
    context="Look for main modules and dependencies"
)

piece2 = PayloadDiscoveryPiece(
    number=2, 
    instruction="Identify entry points",
    context="Find main functions and CLI interfaces"
)

# Create a discovery sequence
discovery = PayloadDiscovery(
    title="Codebase Analysis Workflow",
    pieces=[piece1, piece2]
)

# Use the sequence
for piece in discovery.pieces:
    print(f"Step {piece.number}: {piece.instruction}")
    if piece.context:
        print(f"Context: {piece.context}")
```

### MCP Server Usage

Start the MCP server:

```bash
payload-discovery-mcp
```

The server provides tools for:
- Creating new discovery sequences
- Loading existing sequences
- Navigating through instruction steps
- Saving workflow progress

## Core Concepts

### PayloadDiscoveryPiece
Individual instruction with:
- `number`: Step number in sequence
- `instruction`: What to do
- `context`: Additional guidance/information

### PayloadDiscovery
Collection of pieces forming a complete workflow:
- `title`: Name of the workflow
- `pieces`: Ordered list of instructions
- `metadata`: Additional workflow information

## Use Cases

- **Agent Workflows**: Systematic task completion
- **Code Analysis**: Structured codebase exploration
- **Quality Assurance**: Step-by-step validation processes
- **Onboarding**: Guided learning sequences
- **Debugging**: Systematic problem-solving approaches

## Integration with HEAVEN Ecosystem

Payload Discovery integrates with:
- **Waypoint**: For navigation through sequences
- **STARLOG**: For tracking sequence completion
- **Powerset Agents**: For systematic agent workflows

## Development

```bash
# Clone and install for development
git clone https://github.com/sancovp/payload-discovery
cd payload-discovery
pip install -e ".[dev]"

# Run tests
pytest

# Start development MCP server
python -m payload_discovery.mcp_server_v2
```

## License

MIT License - see LICENSE file for details.

## Part of HEAVEN Ecosystem

This library is part of the HEAVEN (Hierarchical Event-based Agent-Versatile Environment Network) ecosystem for AI agent development.