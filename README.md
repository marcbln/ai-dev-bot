# DevBot

Autonomous DevOps Agent.

## Setup
1. `uv venv`
2. `source .venv/bin/activate`
3. `uv pip install -e ".[dev]"`
4. Create `.env` file with keys.

## Usage
1. Start Watcher: `python -m devbot.cli watch`
2. Start Server: `python -m devbot.cli server`
3. Drop a markdown plan into `ai-docs/`.

## Workflow
1. User creates `ai-docs/feature.md`.
2. Agent reads plan, creates branch `devbot/feature`.
3. Agent writes code, **executes tests to verify**, commits, pushes.
4. Agent creates PR.
5. If Reviewer requests changes on GitHub, Agent **autonomously iterates and fixes code**.
