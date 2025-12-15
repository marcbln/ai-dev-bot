import os
import subprocess
from pathlib import Path

from devbot.interfaces import IFileSystem, IShellOps


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
                if any(skip in root for skip in (".git", "__pycache__", ".venv", ".pytest_cache")):
                    continue
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            return "\n".join(files)
        except Exception as e:
            return f"Error listing files: {e}"


class ShellTools(IShellOps):
    def execute_command(self, command: str) -> str:
        try:
            # Security Note: In production, this should be sandboxed.
            print(f"Executing: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout
            )
            output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            if result.returncode != 0:
                output += f"\nExit Code: {result.returncode}"
            return output if output.strip() else "Command executed with no output."
        except subprocess.TimeoutExpired:
            return "Error: Command timed out."
        except Exception as e:
            return f"Error executing command: {e}"
