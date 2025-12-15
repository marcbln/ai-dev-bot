import datetime
import time
from typing import Optional, Set, List, Dict

import anthropic

from devbot.config import config
from devbot.git_ops import GitOps
from devbot.interfaces import IFileSystem, IGitOps, IShellOps
from devbot.tools import FileSystemTools, ShellTools


class Agent:
    def __init__(
        self,
        fs: Optional[IFileSystem] = None,
        git: Optional[IGitOps] = None,
        shell: Optional[IShellOps] = None
    ) -> None:
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.tools = fs if fs else FileSystemTools()
        self.git = git if git else GitOps()
        self.shell = shell if shell else ShellTools()
        self.model = "claude-3-5-sonnet-20240620"
        self.files_created: Set[str] = set()
        self.files_modified: Set[str] = set()

    def run_task(self, plan_path: str, task_name: str) -> None:
        print(f"Starting task: {task_name}")
        self._reset_state()
        plan_content = self.tools.read_file(plan_path)
        branch_name = f"devbot/{task_name}-{int(time.time())}"
        self.git.create_branch(branch_name)

        messages = [
            {
                "role": "user",
                "content": f"Here is the plan:\n{plan_content}\n\nList the files to understand the repo structure first.",
            }
        ]

        self._run_loop(messages, branch_name, plan_content=plan_content)

    def iterate_on_feedback(self, branch_name: str, feedback: str) -> None:
        print(f"Iterating on {branch_name} with feedback")
        self.git.checkout_branch(branch_name)
        self._reset_state()

        messages = [
            {
                "role": "user",
                "content": (
                    f"I have reviewed your PR on branch '{branch_name}'. "
                    f"Here is the feedback:\n\n{feedback}\n\n"
                    "Please read the relevant files, fix the code, run tests using EXEC_CMD, "
                    "and then output DONE <commit_message>."
                ),
            }
        ]

        self._run_loop(messages, branch_name, is_feedback_mode=True)

    def _reset_state(self) -> None:
        self.files_created.clear()
        self.files_modified.clear()

    def _get_system_prompt(self) -> str:
        return (
            "You are an autonomous senior DevOps engineer.\n"
            "Your goal is to implement the user's plan by reading code, modifying files,"
            " running tests, and ensuring the project runs.\n\n"
            "You have the following tools available. Output the command as the FIRST line of your response:\n"
            "1. READ_FILE <path>\n"
            "2. WRITE_FILE <path>\n<<<<\ncontent\n>>>>\n"
            "3. LIST_FILES <path>\n"
            "4. EXEC_CMD <shell_command>\n"
            "5. DONE <pr_title_or_commit_message>\n<<<<\npr_description (optional)\n>>>>\n\n"
            "Use EXEC_CMD to verify your changes (e.g., `uv run pytest` or `python -m ...`)."
        )

    def _run_loop(
        self,
        messages: List[Dict[str, str]],
        branch_name: str,
        plan_content: str = "",
        is_feedback_mode: bool = False
    ) -> None:

        for _ in range(20): # Increased step limit for testing
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=self._get_system_prompt(),
                    messages=messages,
                )
                reply = response.content[0].text
                print(f"\n[AI]: {reply[:100]}...")
                messages.append({"role": "assistant", "content": reply})

                if "DONE" in reply:
                    self._handle_completion(reply, branch_name, plan_content, is_feedback_mode)
                    if not is_feedback_mode:
                        self._generate_report(branch_name) # simplified arg
                    break

                tool_output = self._execute_tool(reply)
                messages.append({"role": "user", "content": f"Tool Output:\n{tool_output}"})

            except Exception as e:
                print(f"Error in execution loop: {e}")
                break

    def _execute_tool(self, reply: str) -> str:
        lines = reply.split("\n")
        command_line = lines[0].strip()

        if command_line.startswith("READ_FILE"):
            path = command_line.split(" ", 1)[1]
            return self.tools.read_file(path)

        if command_line.startswith("LIST_FILES"):
            path = command_line.split(" ", 1)[1] if " " in command_line else "."
            return self.tools.list_files(path)

        if command_line.startswith("EXEC_CMD"):
            cmd = command_line.split(" ", 1)[1]
            return self.shell.execute_command(cmd)

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

    def _handle_completion(self, reply: str, branch_name: str, plan_content: str, is_feedback_mode: bool) -> None:
        try:
            lines = reply.split("\n")
            cmd_line = lines[0]
            title = cmd_line.replace("DONE", "").strip()

            if is_feedback_mode:
                # Just commit and push fixes
                self.git.commit_changes(f"Fixes: {title}")
                self.git.push_changes(branch_name)
            else:
                # Create PR for new tasks
                body = plan_content
                if "<<<<" in reply:
                    body = reply.split("<<<<")[1].split(">>>>")[0].strip()

                self.git.commit_changes(f"Implemented: {title}")
                self.git.push_changes(branch_name)
                self.git.create_pr(branch_name, title, body)

        except Exception as exc:
            print(f"Error finishing task: {exc}")

    def _generate_report(self, task_name: str) -> None:
        # Simplified report generation logic for brevity
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        yy_mm_dd = datetime.datetime.now().strftime("%y%m%d")
        safe_name = task_name.replace("devbot/", "")
        report_filename = f"ai-plans/{yy_mm_dd}__IMPLEMENTATION_REPORT__{safe_name}.md"

        created_list = "\n".join([f"- {f}" for f in sorted(self.files_created)]) or "None"
        modified_list = "\n".join([f"- {f}" for f in sorted(self.files_modified)]) or "None"

        content = f"""---
filename: "{report_filename}"
title: "Report: {safe_name}"
createdAt: {timestamp}
updatedAt: {timestamp}
status: completed
files_created: {len(self.files_created)}
files_modified: {len(self.files_modified)}
files_deleted: 0
tags: [report, automated]
documentType: IMPLEMENTATION_REPORT
---

# Summary
Task executed autonomously.

# Files Changed
## Created
{created_list}

## Modified
{modified_list}
"""
        self.tools.write_file(report_filename, content)
        print(f"Report generated: {report_filename}")
