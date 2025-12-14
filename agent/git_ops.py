from git import Repo  # type: ignore
from github import Github  # type: ignore

from agent.config import config


class GitOps:
    def __init__(self):
        self.repo = Repo(".")
        self.gh = Github(config.GITHUB_TOKEN)
        self.gh_repo = self.gh.get_repo(config.REPO_NAME)

    def create_branch(self, branch_name: str) -> None:
        self.repo.git.checkout("main")
        self.repo.git.pull()
        branch = self.repo.create_head(branch_name)
        branch.checkout()
        print(f"Switched to new branch: {branch_name}")

    def checkout_branch(self, branch_name: str) -> None:
        self.repo.git.checkout(branch_name)
        self.repo.git.pull()
        print(f"Checked out {branch_name}")

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
