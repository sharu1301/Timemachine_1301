# dt-timemachine

An MCP (Model Context Protocol) proxy for Dynatrace designed to evaluate AI SRE agents. 

This proxy sits between an AI Agent and the Dynatrace MCP server, logging all tool calls and (in future weeks) clamping DQL time ranges to simulate "time travel" incident replay.

## Current Status: Week 1 Complete ✅

- **Transparent Passthrough:** Forwards tools and requests from the agent to Dynatrace without modification.
- **JSONL Logging:** Every tool call, argument, and response is logged to `runs/` for later analysis.
- **Dual Transports:** Supports both local `stdio` (for fake upstream testing) and remote `HTTP` (for Dynatrace's SaaS MCP Gateway).
- **Windows Compatible:** Includes custom argument splitting to handle Windows paths and PowerShell execution policies.

## Setup

1. Clone the repo and create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
