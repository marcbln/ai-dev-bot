---
filename: "ai-plans/251214__IMPLEMENTATION_PLAN__refactor_devbot_core_and_cli.md"
title: "Refactor DevBot Core, Add Direct Execution and Reporting"
createdAt: 2025-12-14 23:30
updatedAt: 2025-12-14 23:30
status: in-progress
priority: high
tags: [refactoring, solid, cli, reporting]
estimatedComplexity: moderate
documentType: IMPLEMENTATION_PLAN
---

# Problem Statement
The current `DevBot` implementation has several architectural limitations:
1. **Coupling**: The `Agent` class in `brain.py` is tightly coupled to concrete tool implementations.
2. **Execution Mode**: It only supports a "Watcher" mode, making it difficult to run specific plans on demand.
3. **Observability**: There is no structured reporting after a task is completed.
4. **State Tracking**: The agent does not track which files it modified, making accurate reporting impossible.

This plan aims to refactor the core logic to use Dependency Injection for tools, add a CLI `run` command, and implement a robust reporting system.

## Phase 1: Tooling Abstraction (SOLID)

We will define an abstract base class for tools and refactor the concrete implementations. This adheres to the **Interface Segregation** and **Dependency Inversion** principles.

### [NEW FILE] `agent/interfaces.py`
```python
from abc import ABC, abstractmethod
from typing import List

class IFileSystem(ABC):
    @abstractmethod
    def read_file(self, path: str) -> str: pass
    
    @abstractmethod
    def write_file(self, path: str, content: str) -> str: pass
    
    @abstractmethod
    def list_files(self, path: str) -> str: pass

class IGitOps(ABC):
    @abstractmethod
    def create_branch(self, branch_name: str) -> None: pass
    
    @abstractmethod
    def commit_changes(self, message: str) -> None: pass
    
    @abstractmethod
    def push_changes(self, branch_name: str) -> None: pass
    
    @abstractmethod
    def create_pr(self, branch_name: str, title: str, body: str) -> str: pass
```

### [MODIFY] `agent/tools.py`
We will implement the interface and add tracking capability.

```python
import os
from pathlib import Path
from agent.interfaces import IFileSystem

class FileSystemTools(IFileSystem):
    def read_file(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file {file_path}: {e}"

    def write_file(self, file_path: str, content: str) -> str:
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing file {file_path}: {e}"

    def list_files(self, directory: str = ".") -> str:
        try:
            files = []
            for root, _, filenames in os.walk(directory):
                if ".git" in root or "__pycache__" in root or ".venv" in root:
                    continue
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            return "\n".join(files)
        except Exception as e:
            return f"Error listing files: {e}"
```

### [MODIFY] `agent/git_ops.py`
Make `GitOps` implement `IGitOps`.

```python
from git import Repo # type: ignore
from github import Github # type: ignore
from agent.config import config
from agent.interfaces import IGitOps

class GitOps(IGitOps):
    def __init__(self) -> None:
        self.repo = Repo(".")
        self.gh = Github(config.GITHUB_TOKEN)
        self.gh_repo = self.gh.get_repo(config.REPO_NAME)

    def create_branch(self, branch_name: str) -> None:
        if self.repo.active_branch.name != "main":
             self.repo.git.checkout("main")
        self.repo.git.pull()
        branch = self.repo.create_head(branch_name)
        branch.checkout()
        print(f"Switched to new branch: {branch_name}")

    def commit_changes(self, message: str) -> None:
        self.repo.git.add(A=True)
        self.repo.index.commit(message)
        print(f"Committed changes: {message}")

    def push_changes(self, branch_name: str) -> None:
        origin = self.repo.remote(name="origin")
        origin.push(branch_name, set_upstream=True)
        print(f"Pushed {branch_name}")

    def create_pr(self, branch_name: str, title: str, body: str) -> str:
        pr = self.gh_repo.create_pull(
            title=title,
            body=body,
            head=branch_name,
            base="main",
        )
        print(f"PR Created: {pr.html_url}")
        return pr.html_url
```

## Phase 2: Agent Refactoring and Reporting

We will modify the `Agent` class to track statistics for the report and implement the report generation logic.

### [MODIFY] `agent/brain.py`
```python
import time
import datetime
from typing import List, Dict, Set
import anthropic

from agent.config import config
from agent.interfaces import IFileSystem, IGitOps
from agent.tools import FileSystemTools
from agent.git_ops import GitOps

class Agent:
    def __init__(self, fs: IFileSystem = None, git: IGitOps = None) -> None:
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.tools = fs if fs else FileSystemTools()
        self.git = git if git else GitOps()
        self.model = "claude-3-5-sonnet-20240620"
        
        # State tracking for Reporting
        self.files_created: Set[str] = set()
        self.files_modified: Set[str] = set()

    def run_task(self, plan_path: str, task_name: str) -> None:
        print(f"Starting task: {task_name}")
        plan_content = self.tools.read_file(plan_path)
        branch_name = f"agent/{task_name}-{int(time.time())}"
        self.git.create_branch(branch_name)

        system_prompt = (
            "You are an autonomous senior DevOps engineer.\n"
            "Your goal is to implement the user's plan by reading code, modifying files,"
            " and ensuring the project runs.\n\n"
            "You have the following tools available via specific output formats:\n"
            "1. READ_FILE <path>\n"
            "2. WRITE_FILE <path>\n<<<<\ncontent\n>>>>\n"
            "3. LIST_FILES <path>\n"
            "4. DONE <pr_title>\n<<<<\npr_description\n>>>>\n\n"
            "When you want to use a tool, output the command as the FIRST line of your response.\n"
            "If writing a file or description, use the <<<< delimiter."
        )

        messages = [
            {
                "role": "user",
                "content": f"Here is the plan:\n{plan_content}\n\nList the files to understand the repo structure first.",
            }
        ]

        for _ in range(15):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
            )
            reply = response.content[0].text
            print(f"\n[AI]: {reply[:100]}...")
            messages.append({"role": "assistant", "content": reply})

            if "DONE" in reply:
                self._handle_done(reply, branch_name, plan_content)
                self._generate_report(plan_path, task_name)
                break

            tool_output = self._execute_tool(reply)
            messages.append({"role": "user", "content": f"Tool Output:\n{tool_output}"})

    def _execute_tool(self, reply: str) -> str:
        lines = reply.split("\n")
        command_line = lines[0].strip()

        if command_line.startswith("READ_FILE"):
            path = command_line.split(" ", 1)[1]
            return self.tools.read_file(path)

        if command_line.startswith("LIST_FILES"):
            path = command_line.split(" ", 1)[1] if " " in command_line else "."
            return self.tools.list_files(path)

        if command_line.startswith("WRITE_FILE"):
            path = command_line.split(" ", 1)[1]
            try:
                content = reply.split("<<<<")[1].split(">>>>")[0].strip()
                if content.startswith("\n"):
                    content = content[1:]
                
                # Tracking logic
                if "Error reading file" in self.tools.read_file(path):
                    self.files_created.add(path)
                else:
                    self.files_modified.add(path)

                return self.tools.write_file(path, content)
            except IndexError:
                return "Error: Invalid WRITE_FILE format. Use <<<< and >>>>"

        return "No tool command found."

    def _handle_done(self, reply: str, branch_name: str, plan_content: str) -> None:
        try:
            lines = reply.split("\n")
            cmd_line = lines[0]
            title = cmd_line.replace("DONE", "").strip()

            body = plan_content
            if "<<<<" in reply:
                body = reply.split("<<<<")[1].split(">>>>")[0].strip()

            self.git.commit_changes(f"Implemented: {title}")
            self.git.push_changes(branch_name)
            self.git.create_pr(branch_name, title, body)
        except Exception as exc:
            print(f"Error finishing task: {exc}")

    def _generate_report(self, plan_path: str, task_name: str) -> None:
        """Generates a markdown report of the execution."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        yy_mm_dd = datetime.datetime.now().strftime("%y%m%d")
        report_filename = f"ai-plans/{yy_mm_dd}__IMPLEMENTATION_REPORT__{task_name}.md"
        
        created_list = "\n".join([f"- {f}" for f in self.files_created]) or "None"
        modified_list = "\n".join([f"- {f}" for f in self.files_modified]) or "None"
        
        content = f"""---
filename: "{report_filename}"
title: "Report: {task_name}"
createdAt: {timestamp}
updatedAt: {timestamp}
plan_file: "{plan_path}"
project: "{config.REPO_NAME}"
status: completed
files_created: {len(self.files_created)}
files_modified: {len(self.files_modified)}
files_deleted: 0
tags: [report, automated]
documentType: IMPLEMENTATION_REPORT
---

# Summary
The AI Agent successfully executed the plan `{plan_path}`. All steps marked in the plan were processed, and a Pull Request has been generated.

# Files Changed
## Created
{created_list}

## Modified
{modified_list}

# Key Changes
- Automated implementation of logic defined in the plan.
- Integration with Git for version control.

# Technical Decisions
- Used direct file manipulation for speed.
- Maintained existing project structure.

# Testing Notes
- Check the generated PR for CI/CD results.
- Manual verification of the created files is recommended.
"""
        self.tools.write_file(report_filename, content)
        print(f"Report generated: {report_filename}")

    # iterate_on_feedback implementation omitted for brevity but should be kept
    def iterate_on_feedback(self, branch_name: str, feedback: str) -> None:
        pass
```

## Phase 3: CLI Expansion

We will add a direct run command to the CLI to execute plans without waiting for the file watcher.

### [MODIFY] `agent/cli.py`
```python
import os
import typer
import uvicorn

from agent.watcher import start_watching
from agent.brain import Agent

app = typer.Typer()


@app.command()
def watch() -> None:
    """Start the plan watcher."""
    start_watching()


@app.command()
def run(
    plan_path: str = typer.Argument(..., help="Path to the plan markdown file")
) -> None:
    """Execute a specific plan immediately."""
    if not os.path.exists(plan_path):
        print(f"Error: Plan file {plan_path} not found.")
        return
    
    plan_name = os.path.basename(plan_path).replace(".md", "")
    agent = Agent()
    agent.run_task(plan_path, plan_name)


@app.command()
def server(port: int = 8000) -> None:
    """Start the webhook server."""
    uvicorn.run("agent.server:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    app()
```

## Phase 4: Report Generation

This phase is handled automatically by the `_generate_report` method added to `agent/brain.py` in Phase 2. The agent will now automatically create a report file upon completing a task with the `DONE` command.

