import os

import typer
import uvicorn

from agent.brain import Agent
from agent.watcher import start_watching

app = typer.Typer(help="DevBot Agent CLI")


@app.command()
def watch() -> None:
    """Start the plan watcher."""
    start_watching()


@app.command()
def run(plan_path: str = typer.Argument(..., help="Path to the plan markdown file")) -> None:
    """Execute a specific plan immediately."""
    if not os.path.exists(plan_path):
        raise typer.BadParameter(f"Plan file {plan_path} not found.")

    plan_name = os.path.basename(plan_path).replace(".md", "")
    Agent().run_task(plan_path, plan_name)


@app.command()
def server(port: int = 8000) -> None:
    """Start the webhook server."""
    uvicorn.run("agent.server:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    app()
