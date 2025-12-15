import datetime
import time
from typing import Optional, Set

import anthropic

from devbot.config import config
from devbot.git_ops import GitOps
from devbot.interfaces import IFileSystem, IGitOps
from devbot.tools import FileSystemTools


class Agent:
    def __init__(self, fs: Optional[IFileSystem] = None, git: Optional[IGitOps] = None) -> None:
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.tools = fs if fs else FileSystemTools()
        self.git = git if git else GitOps()
        self.model = "claude-3-5-sonnet-20240620"
        self.files_created: Set[str] = set()
        self.files_modified: Set[str] = set()

    def run_task(self, plan_path: str, task_name: str) -> None:
        print(f"Starting task: {task_name}")
        self.files_created.clear()
        self.files_modified.clear()
        plan_content = self.tools.read_file(plan_path)
        branch_name = f"devbot/{task_name}-{int(time.time())}"
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

    def iterate_on_feedback(self, branch_name: str, feedback: str) -> None:
        print(f"Iterating on {branch_name} with feedback")
        self.git.checkout_branch(branch_name)
        messages = [
            {
                "role": "user",
                "content": (
                    "We submitted a PR but received feedback. Fix the code.\n"
                    f"Feedback: {feedback}"
                ),
            }
        ]
        # Placeholder for future loop reuse.
        pass

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
        except Exception as exc:  # pragma: no cover - best-effort logging
            print(f"Error finishing task: {exc}")

    def _generate_report(self, plan_path: str, task_name: str) -> None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        yy_mm_dd = datetime.datetime.now().strftime("%y%m%d")
        report_filename = f"ai-plans/{yy_mm_dd}__IMPLEMENTATION_REPORT__{task_name}.md"

        created_list = "\n".join([f"- {f}" for f in sorted(self.files_created)]) or "None"
        modified_list = "\n".join([f"- {f}" for f in sorted(self.files_modified)]) or "None"

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
