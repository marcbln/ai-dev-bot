import typer
import uvicorn

from agent.watcher import start_watching

app = typer.Typer()


@app.command()
def watch() -> None:
    """Start the plan watcher."""
    start_watching()


@app.command()
def server(port: int = 8000) -> None:
    """Start the webhook server."""
    uvicorn.run("agent.server:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    app()
