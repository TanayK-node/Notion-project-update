from fastapi import FastAPI, Request
import requests
import os

#testing1.1
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


print("DEBUG NOTION_TOKEN:", NOTION_TOKEN is not None)
print("DEBUG DATABASE_ID:", DATABASE_ID)

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

app = FastAPI()
#testing logic update

def fetch_github_repos():
    url = "https://api.github.com/user/repos"
    headers_github = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    repos = []
    page = 1

    while True:
        response = requests.get(f"{url}?per_page=100&page={page}", headers=headers_github)
        if response.status_code != 200:
            print("⚠️ GitHub API Error:", response.status_code, response.text)
            break

        data = response.json()
        if not data:
            break  # no more repos

        repos.extend(data)
        page += 1

    return repos


def create_project_in_notion(repo_name, repo_url):
    print("📌 Creating project in Notion...")
    print(f"   Repo: {repo_name}, URL: {repo_url}")

    data = {
        "parent": { "database_id": DATABASE_ID },
        "properties": {
            "Name": {"title": [{"text": {"content": repo_name}}]},
            "GitHub Link": {"url": repo_url},
            #"Status": {"select": {"name": "Done"}},
        }
    }
    response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data)
    print("✅ Notion Response Status:", response.status_code)
    print("🔍 Notion Response Body:", response.text)


def upsert_repo_in_notion(repo_name, repo_url, commit_msg=None, commit_date=None):
    """
    Create or update a repo in Notion.
    If the repo exists, update Last Commit + Date.
    If it doesn't exist, create a new entry.
    """
    print(f"📌 Upserting repo in Notion: {repo_name}")

    # Step 1: Check if repo already exists
    query = requests.post(
        f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
        headers=headers,
        json={"filter": {"property": "Name", "title": {"equals": repo_name}}}
    ).json()

    print("🔍 Query Results:", query)

    if len(query.get("results", [])) > 0:
        # Repo already exists → update
        page_id = query["results"][0]["id"]
        update_data = {
            "properties": {}
        }

        if commit_msg:
            update_data["properties"]["Last Commit"] = {
                "rich_text": [{"text": {"content": commit_msg}}]
            }

        if commit_date:
            update_data["properties"]["Last Commit Date"] = {
                "date": {"start": commit_date}
            }

        response = requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=headers,
            json=update_data
        )
        print("✅ Updated existing repo:", response.status_code, response.text)

    else:
        # Repo does not exist → create new entry
        create_data = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "Name": {"title": [{"text": {"content": repo_name}}]},
                "GitHub Link": {"url": repo_url},
            }
        }

        if commit_msg:
            create_data["properties"]["Last Commit"] = {
                "rich_text": [{"text": {"content": commit_msg}}]
            }

        if commit_date:
            create_data["properties"]["Last Commit Date"] = {
                "date": {"start": commit_date}
            }

        response = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=create_data
        )
        print("✅ Created new repo:", response.status_code, response.text)

def fetch_latest_commit(repo):
    commits_url = repo["commits_url"].replace("{/sha}", "")
    response = requests.get(commits_url, headers={
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    })
    if response.status_code == 200 and response.json():
        latest_commit = response.json()[0]
        return latest_commit["commit"]["message"], latest_commit["commit"]["author"]["date"]
    return None, None


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

    repo_name = payload["repository"]["name"]
    repo_url = payload["repository"]["html_url"]

    commit_msg, commit_date = None, None
    if "commits" in payload and payload["commits"]:
        last_commit = payload["commits"][-1]
        commit_msg = last_commit["message"]
        commit_date = last_commit["timestamp"]

    # Call upsert logic
    upsert_repo_in_notion(repo_name, repo_url, commit_msg, commit_date)

    return {"status": "ok"}

@app.get("/api/sync_repos")
@app.post("/api/sync_repos")
def sync_repos():
    print("📌 Syncing all GitHub repos...")
    repos = fetch_github_repos()

    for repo in repos:
        repo_name = repo["name"]
        repo_url = repo["html_url"]

        commit_msg, commit_date = fetch_latest_commit(repo)

        print(f"➡️ Adding/Updating repo in Notion: {repo_name}")
        upsert_repo_in_notion(repo_name, repo_url, commit_msg, commit_date)

    return {"status": "done", "repos_synced": len(repos)}
