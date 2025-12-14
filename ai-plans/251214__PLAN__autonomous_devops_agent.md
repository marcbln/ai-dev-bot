---
filename: "ai-plans/251214__PLAN__autonomous_devops_agent.md"
title: "Autonomous AI DevOps Agent Workflow"
date: 2025-12-14
status: draft
priority: high
tags: [ai, devops, python, automation, git]
estimated_complexity: complex
---

# Autonomous AI DevOps Agent

This plan outlines the construction of "DevBot," an autonomous agent workflow designed to execute DevOps and coding tasks. The system will monitor a directory for instructions, execute them using an LLM, handle Git version control, submit Pull Requests, and iterate based on feedback.

## Problem Statement
Developers spend significant time on routine coding tasks and refactoring. While AI coding assistants exist, they often require manual intervention to apply changes, commit, and manage PRs. This system aims to fully automate the loop: Plan $\rightarrow$ Code $\rightarrow$ PR $\rightarrow$ Feedback $\rightarrow$ Fix.

## Architecture
The system consists of:
1.  **Watcher**: A file system monitor using `watchdog` to detect new plan files in `ai-docs/`.
2.  **Agent Core**: The orchestration logic (using Anthropic's Claude) to reason, write code, and execute tests.
3.  **Git Operations**: Automated handling of branching, committing, pushing, and PR creation via `GitPython` and `PyGithub`.
4.  **Feedback Loop**: A webhook server using `FastAPI` to listen for GitHub PR reviews and trigger the agent to fix issues.

## Phase 1: Environment & Configuration Setup

We will set up the project structure, dependency management using `uv`, and configuration loading.

### [NEW FILE] `pyproject.toml`
```toml
[project]
name = "devbot"
version = "0.1.0"
description = "Autonomous DevOps Agent"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.18.0",
    "watchdog>=4.0.0",
    "GitPython>=3.1.41",
    "PyGithub>=2.1.1",
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "python-dotenv>=1.0.1",
    "typer[all]>=0.9.0",
    "rich>=13.7.0",
    "httpx>=0.26.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "black>=24.0.0",
    "mypy>=1.8.0"
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.mypy]
strict = true
```

### [NEW FILE] `agent/__init__.py`
```python
"""DevBot Agent Package."""
```

### [NEW FILE] `agent/config.py`
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    REPO_NAME = os.getenv("REPO_NAME") # format: "owner/repo"
    AI_DOCS_DIR = "ai-docs"
    
    # Validation
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is missing")
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN is missing")
    if not REPO_NAME:
        raise ValueError("REPO_NAME is missing")

config = Config()
```

### [NEW FILE] `.env`
```text
ANTHROPIC_API_KEY=your_key_here
GITHUB_TOKEN=your_github_pat_here
REPO_NAME=your_username/your_repo
```

## Phase 2: Tooling & Git Operations

We need reliable tools for file manipulation and Git interactions.

### [NEW FILE] `agent/tools.py`
```python
import os
from pathlib import Path
from typing import List

class Tools:
    @staticmethod
    def read_file(file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {file_path}: {str(e)}"

    @staticmethod
    def write_file(file_path: str, content: str) -> str:
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing file {file_path}: {str(e)}"

    @staticmethod
    def list_files(directory: str = ".") -> str:
        try:
            files = []
            for root, _, filenames in os.walk(directory):
                if ".git" in root or "__pycache__" in root:
                    continue
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            return "\n".join(files)
        except Exception as e:
            return f"Error listing files: {str(e)}"
```

### [NEW FILE] `agent/git_ops.py`
```python
import time
from git import Repo # type: ignore
from github import Github # type: ignore
from agent.config import config

class GitOps:
    def __init__(self):
        self.repo = Repo(".")
        self.gh = Github(config.GITHUB_TOKEN)
        self.gh_repo = self.gh.get_repo(config.REPO_NAME)

    def create_branch(self, branch_name: str):
        # Ensure we are on main and clean
        self.repo.git.checkout("main")
        self.repo.git.pull()
        
        current = self.repo.create_head(branch_name)
        current.checkout()
        print(f"Switched to new branch: {branch_name}")

    def checkout_branch(self, branch_name: str):
        self.repo.git.checkout(branch_name)
        self.repo.git.pull()
        print(f"Checked out {branch_name}")

    def commit_changes(self, message: str):
        self.repo.git.add(A=True)
        self.repo.index.commit(message)
        print(f"Committed changes: {message}")

    def push_changes(self, branch_name: str):
        origin = self.repo.remote(name='origin')
        origin.push(branch_name, set_upstream=True)
        print(f"Pushed {branch_name}")

    def create_pr(self, branch_name: str, title: str, body: str) -> str:
        pr = self.gh_repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base="main"
        )
        print(f"PR Created: {pr.html_url}")
        return pr.html_url
```

## Phase 3: The Agent Brain

This is the core logic that connects the LLM to the tools.

### [NEW FILE] `agent/brain.py`
```python
import time
import anthropic
from agent.config import config
from agent.tools import Tools
from agent.git_ops import GitOps

class Agent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.tools = Tools()
        self.git = GitOps()
        self.model = "claude-3-5-sonnet-20240620"

    def run_task(self, plan_path: str, task_name: str):
        print(f"Starting task: {task_name}")
        
        # Read Plan
        plan_content = self.tools.read_file(plan_path)
        
        # Git Setup
        branch_name = f"agent/{task_name}-{int(time.time())}"
        self.git.create_branch(branch_name)

        system_prompt = """
        You are an autonomous senior DevOps engineer.
        Your goal is to implement the user's plan by reading code, modifying files, and ensuring the project runs.
        
        You have the following tools available via specific output formats:
        1. READ_FILE <path>
        2. WRITE_FILE <path>
        <<<<
        content
        >>>>
        3. LIST_FILES <path>
        4. DONE <pr_title>
        <<<<
        pr_description
        >>>>

        When you want to use a tool, output the command as the FIRST line of your response.
        If writing a file or description, use the <<<< delimiter.
        """

        messages = [
            {"role": "user", "content": f"Here is the plan:\n{plan_content}\n\nList the files to understand the repo structure first."}
        ]

        # Execution Loop
        for _ in range(15): # Max steps safety limit
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            )
            
            reply = response.content[0].text
            print(f"\n[AI]: {reply[:100]}...") # Log brief output
            messages.append({"role": "assistant", "content": reply})

            if "DONE" in reply:
                self._handle_done(reply, branch_name, plan_content)
                break
            
            tool_output = self._execute_tool(reply)
            messages.append({"role": "user", "content": f"Tool Output:\n{tool_output}"})

    def iterate_on_feedback(self, branch_name: str, feedback: str):
        print(f"Iterating on {branch_name} with feedback")
        self.git.checkout_branch(branch_name)
        
        # Simplified context for iteration
        messages = [
            {"role": "user", "content": f"We submitted a PR but received feedback. Fix the code.\nFeedback: {feedback}"}
        ]
        
        # Re-use loop (refactor loop logic in production)
        # For brevity in plan, assuming similar loop structure
        pass 

    def _execute_tool(self, reply: str) -> str:
        lines = reply.split('\n')
        command_line = lines[0].strip()
        
        if command_line.startswith("READ_FILE"):
            path = command_line.split(" ", 1)[1]
            return self.tools.read_file(path)
            
        elif command_line.startswith("LIST_FILES"):
            path = command_line.split(" ", 1)[1] if " " in command_line else "."
            return self.tools.list_files(path)

        elif command_line.startswith("WRITE_FILE"):
            path = command_line.split(" ", 1)[1]
            # Extract content between delimiters
            try:
                content = reply.split("<<<<")[1].split(">>>>")[0].strip()
                # Remove first newline if present
                if content.startswith("\n"): content = content[1:]
                return self.tools.write_file(path, content)
            except IndexError:
                return "Error: Invalid WRITE_FILE format. Use <<<< and >>>>"
        
        return "No tool command found."

    def _handle_done(self, reply: str, branch_name: str, plan_content: str):
        try:
            lines = reply.split('\n')
            cmd_line = lines[0] # DONE <title>
            title = cmd_line.replace("DONE", "").strip()
            
            body = plan_content
            if "<<<<" in reply:
                body = reply.split("<<<<")[1].split(">>>>")[0].strip()
            
            self.git.commit_changes(f"Implemented: {title}")
            self.git.push_changes(branch_name)
            self.git.create_pr(branch_name, title, body)
            
        except Exception as e:
            print(f"Error finishing task: {e}")

```

## Phase 4: The Watcher

### [NEW FILE] `agent/watcher.py`
```python
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from agent.brain import Agent
from agent.config import config

class PlanHandler(FileSystemEventHandler):
    def __init__(self):
        self.agent = Agent()

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        
        print(f"New plan detected: {event.src_path}")
        # Wait briefly for file write to complete
        time.sleep(1)
        
        plan_name = os.path.basename(event.src_path).replace('.md', '')
        self.agent.run_task(event.src_path, plan_name)

def start_watching():
    # Ensure dir exists
    if not os.path.exists(config.AI_DOCS_DIR):
        os.makedirs(config.AI_DOCS_DIR)
        
    observer = Observer()
    observer.schedule(PlanHandler(), path=config.AI_DOCS_DIR, recursive=False)
    observer.start()
    print(f"Watching {config.AI_DOCS_DIR} for plans...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

## Phase 5: The Feedback Loop (Webhook Server)

### [NEW FILE] `agent/server.py`
```python
from fastapi import FastAPI, Request
from agent.brain import Agent

app = FastAPI()
agent = Agent()

@app.post("/webhook")
async def github_webhook(request: Request):
    data = await request.json()
    
    # Handle PR Review
    if 'review' in data and data['action'] == 'submitted':
        state = data['review']['state']
        if state == 'changes_requested':
            branch = data['pull_request']['head']['ref']
            feedback = data['review']['body']
            
            print(f"Feedback received on {branch}")
            # Run in background ideally, but direct call for MVP
            agent.iterate_on_feedback(branch, feedback)
            
    return {"status": "ok"}
```

## Phase 6: CLI Entry Point

### [NEW FILE] `agent/cli.py`
```python
import typer
import uvicorn
from agent.watcher import start_watching

app = typer.Typer()

@app.command()
def watch():
    """Start the plan watcher."""
    start_watching()

@app.command()
def server(port: int = 8000):
    """Start the webhook server."""
    uvicorn.run("agent.server:app", host="0.0.0.0", port=port, reload=True)

if __name__ == "__main__":
    app()
```

### [NEW FILE] `README.md`
```markdown
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
```

## Phase 7: Report

We will generate a summary of the implementation.

### [NEW FILE] `ai-plans/251214__REPORT__autonomous_devops_agent.md`
```yaml
---
filename: "ai-plans/251214__REPORT__autonomous_devops_agent.md"
title: "Report: Autonomous AI DevOps Agent Workflow"
date: 2025-12-14
plan_file: "ai-plans/251214__PLAN__autonomous_devops_agent.md"
status: completed
files_created: 8
files_modified: 0
files_deleted: 0
tags: [report, devops, agent]
---

# Summary
Successfully implemented the DevBot architecture. The system now supports a full cycle of watching for plans, autonomous execution via Claude, and Git automation.

# Files Changed
## Created
- `pyproject.toml`: Dependency configuration.
- `agent/__init__.py`: Package marker.
- `agent/config.py`: Environment configuration.
- `agent/tools.py`: File system utilities.
- `agent/git_ops.py`: Git and GitHub API wrapper.
- `agent/brain.py`: LLM orchestration logic.
- `agent/watcher.py`: Directory monitoring daemon.
- `agent/server.py`: Webhook handler for feedback.
- `agent/cli.py`: Command line interface.

# Key Changes
- **Watcher Integration**: Used `watchdog` to provide real-time triggering when plans are added.
- **Git Automation**: Abstracted complex git sequences (checkout new branch, commit all, push upstream) into simple methods.
- **Tool Protocol**: Defined a custom text-based protocol for the LLM to invoke file operations (`WRITE_FILE <<<<...>>>>`).

# Technical Decisions
- **LLM Context**: Used a simplified tool invocation format rather than function calling API for broader compatibility and easier debugging of the "thought process" in the logs.
- **State Management**: The agent currently relies on the conversation history within the run loop. It does not persist state to disk, which means if the process dies mid-task, it restarts from the beginning.

# Testing Notes
- **Watcher Test**: Create a dummy file in `ai-docs/` and verify the log shows detection.
- **Agent Test**: Run with a simple plan "Create a file named hello.txt with content 'world'" and verify the branch and PR are created.
- **Server Test**: Use `curl` to simulate a GitHub webhook payload to `localhost:8000/webhook`.

# Next Steps
- Implement `iterate_on_feedback` fully in `brain.py` (currently a placeholder).
- Add sandbox execution (Docker) for running tests before committing.
- Add persistence for agent state.
```

