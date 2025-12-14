import os
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from agent.brain import Agent
from agent.config import config


class PlanHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        self.agent = Agent()

    def on_created(self, event):  # type: ignore[override]
        if event.is_directory or not event.src_path.endswith(".md"):
            return

        print(f"New plan detected: {event.src_path}")
        time.sleep(1)
        plan_name = os.path.basename(event.src_path).replace(".md", "")
        self.agent.run_task(event.src_path, plan_name)


def start_watching() -> None:
    if not os.path.exists(config.AI_DOCS_DIR):
        os.makedirs(config.AI_DOCS_DIR)

    observer = Observer()
    observer.schedule(PlanHandler(), path=config.AI_DOCS_DIR, recursive=False)
    observer.start()
    print(f"Watching {config.AI_DOCS_DIR} for plans...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
