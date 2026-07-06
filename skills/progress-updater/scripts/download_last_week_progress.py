import csv
import os
import pathlib
import re
from typing import Any

import requests

from clickup_env import load_clickup_env_from_venv


load_clickup_env_from_venv()

CLICKUP_TOKEN = os.getenv("CLICKUP_TOKEN")
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
PROJECTS_PATHS = [
    BASE_DIR / "assets" / "projects_list.csv",
    BASE_DIR / "assets" / "project_list.csv",
]
OUTPUT_PATH = BASE_DIR / "assets" / "last_week_progress.csv"


def comment_date(comment: dict[str, Any]) -> int:
    for key in ("date", "date_created", "date_updated"):
        value = comment.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return 0


def comment_text(comment: dict[str, Any]) -> str:
    for key in ("comment_text", "text_content", "comment"):
        value = comment.get(key)
        if isinstance(value, str):
            return value.strip()
    return ""


def extract_this_week_progress(text: str) -> str:
    match = re.search(
        r"#\s*This Week's Progress:?\s*(.*?)(?=\n#\s*Next Week's Plan:?\s*|\Z)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return text.strip()

    return match.group(1).strip()


def fetch_latest_comment(task_id: str, headers: dict[str, str]) -> dict[str, Any] | None:
    url = f"https://api.clickup.com/api/v2/task/{task_id}/comment"
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    comments = response.json().get("comments", [])
    if not comments:
        return None

    return max(comments, key=comment_date)


def main():
    if not CLICKUP_TOKEN:
        raise SystemExit("Missing environment variable: CLICKUP_TOKEN")

    projects_path = next((path for path in PROJECTS_PATHS if path.exists()), None)
    if not projects_path:
        raise SystemExit(
            "Could not find a project list: "
            + " or ".join(str(path) for path in PROJECTS_PATHS)
        )

    headers = {
        "accept": "application/json",
        "Authorization": CLICKUP_TOKEN,
    }

    rows = []
    with projects_path.open(newline="", encoding="utf-8") as f:
        for project in csv.DictReader(f):
            task_id = (project.get("id") or "").strip()
            task_name = (project.get("name") or "").strip()

            row = {
                "id": task_id,
                "name": task_name,
                "last_comment_id": "",
                "last_comment_date": "",
                "last_week_progress": "",
                "last_comment_text": "",
                "error": "",
            }

            if not task_id:
                row["error"] = "missing id"
                rows.append(row)
                continue

            try:
                latest_comment = fetch_latest_comment(task_id, headers)
            except requests.RequestException as e:
                row["error"] = str(e)
                rows.append(row)
                continue

            if not latest_comment:
                row["error"] = "no comments"
                rows.append(row)
                continue

            text = comment_text(latest_comment)
            row["last_comment_id"] = str(latest_comment.get("id", ""))
            row["last_comment_date"] = str(
                latest_comment.get("date")
                or latest_comment.get("date_created")
                or latest_comment.get("date_updated")
                or ""
            )
            row["last_week_progress"] = extract_this_week_progress(text)
            row["last_comment_text"] = text
            rows.append(row)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "name",
                "last_comment_id",
                "last_comment_date",
                "last_week_progress",
                "last_comment_text",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Created {OUTPUT_PATH} with {len(rows)} projects")


if __name__ == "__main__":
    main()
