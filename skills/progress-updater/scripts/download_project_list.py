import os
import pathlib
import requests
import csv

from clickup_env import load_clickup_env_from_venv


load_clickup_env_from_venv()

CLICKUP_TOKEN = os.getenv("CLICKUP_TOKEN")
CLICKUP_LIST_ID = os.getenv("CLICKUP_LIST_ID")

output = pathlib.Path(__file__).parent.parent / 'assets' / 'projects_list.csv'

if not CLICKUP_TOKEN:
    raise SystemExit("找不到環境變數 CLICKUP_TOKEN")

if not CLICKUP_LIST_ID:
    raise SystemExit("找不到環境變數 CLICKUP_LIST_ID")

headers = {
    "accept": "application/json",
    "Authorization": CLICKUP_TOKEN
}

tasks = []
page = 0

while True:
    url = (
        f"https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task"
        "?archived=false&include_markdown_description=false&include_closed=false"
        f"&page={page}"
    )
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    page_tasks = response.json().get('tasks', [])

    if not page_tasks:
        break

    tasks.extend(page_tasks)
    page += 1

output.parent.mkdir(parents=True, exist_ok=True)
with output.open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'name', 'text_content'])
    writer.writerows([task['id'], task['name'], task['text_content']] for task in tasks)

print(f"已更新 {output}，共 {len(tasks)} 筆任務")

