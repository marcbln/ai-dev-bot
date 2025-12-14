from fastapi import FastAPI, Request

from agent.brain import Agent

app = FastAPI()
agent = Agent()


@app.post("/webhook")
async def github_webhook(request: Request) -> dict[str, str]:
    data = await request.json()

    if "review" in data and data.get("action") == "submitted":
        state = data["review"].get("state")
        if state == "changes_requested":
            branch = data["pull_request"]["head"]["ref"]
            feedback = data["review"].get("body", "")
            print(f"Feedback received on {branch}")
            agent.iterate_on_feedback(branch, feedback)

    return {"status": "ok"}
