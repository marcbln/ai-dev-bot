# DevBot

Autonomous DevOps Agent.

## Setup
1. `uv venv`
2. `source .venv/bin/activate`
3. `uv pip install -e ".[dev]"`
4. Create `.env` file with keys.

## Usage
1. Start Watcher: `python -m agent.cli watch`
2. Start Server: `python -m agent.cli server`
3. Drop a markdown plan into `ai-docs/`.

## Workflow
1. User creates `ai-docs/feature.md`.
2. Agent reads plan, creates branch `agent/feature`.
3. Agent writes code, commits, pushes.
4. Agent creates PR.
5. If Reviewer requests changes, Agent iterates.
