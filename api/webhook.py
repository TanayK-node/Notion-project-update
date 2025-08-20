from fastapi import FastAPI, Request
import requests
import os

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

app = FastAPI()

def create_project_in_notion(repo_name, repo_url):
    data = {
        "parent": { "database_id": DATABASE_ID },
        "properties": {
            "Name": {"title": [{"text": {"content": repo_name}}]},
            "GitHub Link": {"url": repo_url},
            "Status": {"select": {"name": "Ongoing"}},
        }
    }
    requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)

def update_last_commit(repo_name, commit_msg, commit_date):
    query = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=headers,
        json={"filter": {"property": "Name", "title": {"equals": repo_name}}}
    ).json()

    if len(query.get("results", [])) > 0:
        page_id = query["results"][0]["id"]
        data = {
            "properties": {
                "Last Commit": {"rich_text": [{"text": {"content": commit_msg}}]},
                "Last Commit Date": {"date": {"start": commit_date}}
            }
        }
        requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json=data)

@app.get("/")
def root():
    return {"status": "running"}

@app.post("/api/webhook")
async def webhook(request: Request):
    payload = await request.json()

    if "repository" in payload:
        repo_name = payload["repository"]["name"]
        repo_url = payload["repository"]["html_url"]
        create_project_in_notion(repo_name, repo_url)

    if "commits" in payload:
        repo_name = payload["repository"]["name"]
        last_commit = payload["commits"][-1]
        commit_msg = last_commit["message"]
        commit_date = last_commit["timestamp"]
        update_last_commit(repo_name, commit_msg, commit_date)

    return {"status": "ok"}
