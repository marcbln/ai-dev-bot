import time

import anthropic

from agent.config import config
from agent.git_ops import GitOps
from agent.tools import Tools


class Agent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.tools = Tools()
        self.git = GitOps()
        self.model = "claude-3-5-sonnet-20240620"

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
