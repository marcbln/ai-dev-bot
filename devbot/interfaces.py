from abc import ABC, abstractmethod


class IFileSystem(ABC):
    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read the contents of a file and return it as a string."""
        raise NotImplementedError

    @abstractmethod
    def write_file(self, path: str, content: str) -> str:
        """Write content to a file and return a status message."""
        raise NotImplementedError

    @abstractmethod
    def list_files(self, path: str) -> str:
        """List files under the provided path and return the listing as a string."""
        raise NotImplementedError


class IShellOps(ABC):
    @abstractmethod
    def execute_command(self, command: str) -> str:
        """Execute a shell command and return stdout/stderr."""
        raise NotImplementedError

class IGitOps(ABC):
    @abstractmethod
    def create_branch(self, branch_name: str) -> None:
        """Create and checkout a new branch."""
        raise NotImplementedError

    @abstractmethod
    def checkout_branch(self, branch_name: str) -> None:
        """Checkout an existing branch."""
        raise NotImplementedError

    @abstractmethod
    def commit_changes(self, message: str) -> None:
        """Commit staged changes with a message."""
        raise NotImplementedError

    @abstractmethod
    def push_changes(self, branch_name: str) -> None:
        """Push the current branch to the remote."""
        raise NotImplementedError

    @abstractmethod
    def create_pr(self, branch_name: str, title: str, body: str) -> str:
        """Create a pull request and return its URL."""
        raise NotImplementedError
