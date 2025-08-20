from fastapi import FastAPI, Request
import requests
import os

#testing1.1
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

app = FastAPI()

def create_project_in_notion(repo_name, repo_url):
    print("📌 Creating project in Notion...")
    print(f"   Repo: {repo_name}, URL: {repo_url}")

    data = {
        "parent": { "database_id": DATABASE_ID },
        "properties": {
            "Name": {"title": [{"text": {"content": repo_name}}]},
            "GitHub Link": {"url": repo_url},
            "Status": {"select": {"name": "Ongoing"}},
        }
    }
    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
    print("✅ Notion Response Status:", response.status_code)
    print("🔍 Notion Response Body:", response.text)


def update_last_commit(repo_name, commit_msg, commit_date):
    print(f"📌 Updating last commit for {repo_name}...")
    print(f"   Commit Msg: {commit_msg}")
    print(f"   Commit Date: {commit_date}")

    query = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=headers,
        json={"filter": {"property": "Name", "title": {"equals": repo_name}}}
    ).json()

    print("🔍 Query Results:", query)

    if len(query.get("results", [])) > 0:
        page_id = query["results"][0]["id"]
        data = {
            "properties": {
                "Last Commit": {"rich_text": [{"text": {"content": commit_msg}}]},
                "Last Commit Date": {"date": {"start": commit_date}}
            }
        }
        response = requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json=data)
        print("✅ Notion Update Status:", response.status_code)
        print("🔍 Notion Update Body:", response.text)
    else:
        print("⚠️ No Notion page found for repo:", repo_name)


@app.get("/")
def root():
    return {"status": "running"}

@app.get("/api/webhook")
def webhook_status():
    return {"status": "webhook endpoint active"}

@app.post("/api/webhook")
async def webhook(request: Request):
    payload = await request.json()
    print("📥 Webhook received:", payload.keys())

    if "repository" in payload:
        repo_name = payload["repository"]["name"]
        repo_url = payload["repository"]["html_url"]
        print(f"📌 Creating project in Notion: {repo_name} ({repo_url})")
        create_project_in_notion(repo_name, repo_url)

    if "commits" in payload and payload["commits"]:
        repo_name = payload["repository"]["name"]
        last_commit = payload["commits"][-1]
        commit_msg = last_commit["message"]
        commit_date = last_commit["timestamp"]
        print(f"📝 Updating last commit in Notion: {commit_msg} at {commit_date}")
        update_last_commit(repo_name, commit_msg, commit_date)

    return {"status": "ok"}

