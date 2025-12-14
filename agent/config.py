import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    REPO_NAME = os.getenv("REPO_NAME")  # format: "owner/repo"
    AI_DOCS_DIR = "ai-docs"

    # Validation
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is missing")
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN is missing")
    if not REPO_NAME:
        raise ValueError("REPO_NAME is missing")


config = Config()
