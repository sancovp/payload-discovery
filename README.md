# Payload Discovery

A system for creating numbered instruction sequences that agents can systematically follow to complete complex workflows.

## Overview

Payload Discovery provides a structured approach to breaking down complex tasks into numbered, sequential instructions that AI agents can follow systematically. This enables consistent, repeatable workflows while maintaining flexibility for different use cases.

## Key Features

- 📋 **Numbered Sequences**: Create structured, ordered instruction lists
- 🔄 **Systematic Workflows**: Agents can follow sequences step-by-step
- 💾 **Persistent Storage**: Save and reload discovery sequences
- 🛠 **MCP Integration**: Available as MCP server for agent consumption
- 🎯 **Flexible Targeting**: Sequences can be customized for different contexts

## Quick Start

### Installation

```bash
pip install payload-discovery
```

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