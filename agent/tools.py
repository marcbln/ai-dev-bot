import os
from pathlib import Path

from agent.interfaces import IFileSystem


class FileSystemTools(IFileSystem):
    def read_file(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:  # pragma: no cover - simple utility
            return f"Error reading file {file_path}: {e}"

    def write_file(self, file_path: str, content: str) -> str:
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:  # pragma: no cover
            return f"Error writing file {file_path}: {e}"

    def list_files(self, directory: str = ".") -> str:
        try:
            files = []
            for root, _, filenames in os.walk(directory):
                if any(skip in root for skip in (".git", "__pycache__", ".venv")):
                    continue
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            return "\n".join(files)
        except Exception as e:  # pragma: no cover
            return f"Error listing files: {e}"
