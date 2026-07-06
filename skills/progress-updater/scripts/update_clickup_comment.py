import argparse
import html
import json
import os
import re
import secrets
import threading
import webbrowser

import requests
from flask import Flask, request
from werkzeug.serving import make_server

from clickup_env import load_clickup_env_from_venv


load_clickup_env_from_venv()
CLICKUP_TOKEN = os.getenv("CLICKUP_TOKEN")

parser = argparse.ArgumentParser()
parser.add_argument("--task-id", required=True)
parser.add_argument("--task-name", required=True)
parser.add_argument("--content", required=True)
parser.add_argument("--evaluation", default="", help="Evaluation result to display on the confirmation page.")
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8765)

args = parser.parse_args()

TASK_ID = args.task_id
TASK_NAME = args.task_name
DEFAULT_CONTENT = args.content
DEFAULT_EVALUATION = args.evaluation
CONFIRM_TOKEN = secrets.token_urlsafe(32)

app = Flask(__name__)
server = None


def update_clickup(content: str):
    if not CLICKUP_TOKEN:
        raise Exception("找不到環境變數 CLICKUP_TOKEN")

    url = f"https://api.clickup.com/api/v2/task/{TASK_ID}/comment"
    payload = {
        "notify_all": False,
        "comment_text": content,
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": CLICKUP_TOKEN,
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def extract_score(evaluation: str) -> str:
    patterns = [
        r"總分[：:]\s*([0-9]{1,3}\s*/\s*100(?:\s*[（(][^)）]+[)）])?)",
        r"([0-9]{1,3}\s*/\s*100(?:\s*[（(][^)）]+[)）])?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, evaluation)
        if match:
            return match.group(1)
    return "未提供總分"


def parse_score_value(score_text: str) -> int | None:
    match = re.search(r"([0-9]{1,3})\s*/\s*100", score_text)
    if not match:
        match = re.search(r"\b([0-9]{1,3})\b", score_text)
    if not match:
        return None
    return max(0, min(100, int(match.group(1))))


def score_level(score: int | None) -> str:
    if score is None:
        return "N/A"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "E"


def parse_table(lines: list[str], start_index: int) -> tuple[list[dict[str, str]], int]:
    headers: list[str] = []
    rows: list[dict[str, str]] = []
    index = start_index

    while index < len(lines):
        line = lines[index].strip()
        if not line:
            if rows:
                break
            index += 1
            continue
        if line.startswith("## ") and (headers or rows):
            break
        if not line.startswith("|"):
            if headers or rows:
                break
            index += 1
            continue

        cells = [cell.strip() for cell in line.strip("|").split("|")]
        is_separator = all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)
        if is_separator:
            index += 1
            continue
        if not headers:
            headers = cells
        else:
            rows.append(dict(zip(headers, cells)))
        index += 1

    return rows, index


def markdown_table_after_heading(evaluation: str, heading: str) -> list[dict[str, str]]:
    lines = evaluation.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == heading:
            rows, _ = parse_table(lines, index + 1)
            return rows
    return []


def parse_dimension_score(score_text: str) -> tuple[int | None, int | None]:
    match = re.search(r"([0-9]{1,3})\s*/\s*([0-9]{1,3})", score_text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def normalize_json_evaluation(data: dict) -> dict:
    summary = data.get("summary", {})
    dimensions = data.get("dimensions", [])
    comparisons = data.get("comparisons", {})

    score = summary.get("total_score")
    try:
        score = int(score) if score is not None else None
    except (TypeError, ValueError):
        score = None

    normalized_dimensions = []
    for item in dimensions:
        points = item.get("score")
        max_points = item.get("max_score")
        try:
            points = int(points) if points is not None else None
            max_points = int(max_points) if max_points is not None else None
        except (TypeError, ValueError):
            points = None
            max_points = None
        normalized_dimensions.append(
            {
                "name": str(item.get("name", "")),
                "score": points,
                "max_score": max_points,
                "explanation": str(item.get("explanation", "")),
            }
        )

    return {
        "score": score,
        "level": str(summary.get("level") or score_level(score)),
        "judgement": str(summary.get("judgement", "")),
        "dimensions": normalized_dimensions,
        "last_week_comparison": comparisons.get("last_week_plan", []),
        "milestone_comparison": comparisons.get("milestones", []),
        "deductions": data.get("deductions", []),
        "raw": json.dumps(data, ensure_ascii=False, indent=2),
    }


def parse_markdown_evaluation(evaluation: str) -> dict:
    score_text = extract_score(evaluation)
    score = parse_score_value(score_text)
    level_match = re.search(r"[（(]([A-E])[^)）]*[)）]", score_text)
    judgement_match = re.search(r"判斷[：:]\s*(.+)", evaluation)

    dimensions = []
    for row in markdown_table_after_heading(evaluation, "## 分項成績"):
        points, max_points = parse_dimension_score(row.get("分數", ""))
        dimensions.append(
            {
                "name": row.get("維度", ""),
                "score": points,
                "max_score": max_points,
                "explanation": row.get("說明", ""),
            }
        )

    return {
        "score": score,
        "level": level_match.group(1) if level_match else score_level(score),
        "judgement": judgement_match.group(1).strip() if judgement_match else "",
        "dimensions": dimensions,
        "last_week_comparison": markdown_table_after_heading(evaluation, "## 與上次更新比較"),
        "milestone_comparison": markdown_table_after_heading(evaluation, "## 與里程碑比較"),
        "deductions": markdown_table_after_heading(evaluation, "## 資訊不足與扣分註記"),
        "raw": evaluation,
    }


def parse_evaluation(evaluation: str) -> dict:
    if not evaluation.strip():
        return {}
    try:
        data = json.loads(evaluation)
    except json.JSONDecodeError:
        return parse_markdown_evaluation(evaluation)
    if isinstance(data, dict):
        return normalize_json_evaluation(data)
    return parse_markdown_evaluation(evaluation)


def status_class(value: str) -> str:
    text = value.lower()
    if any(token in value for token in ("已完成", "符合進度", "提前")):
        return "status-good"
    if any(token in value for token in ("部分完成", "有風險", "資料不足")):
        return "status-watch"
    if any(token in value for token in ("延遲", "落後", "未交代", "取消")):
        return "status-risk"
    if "risk" in text:
        return "status-watch"
    return "status-neutral"


def render_dimension_cards(dimensions: list[dict[str, str]]) -> str:
    if not dimensions:
        return '<p class="empty-state">未提供分項評分。</p>'

    cards = []
    for item in dimensions:
        name = html.escape(str(item.get("name", "")))
        explanation = html.escape(str(item.get("explanation", "")))
        score = item.get("score")
        max_score = item.get("max_score")
        percent = 0
        score_label = "N/A"
        if isinstance(score, int) and isinstance(max_score, int) and max_score:
            percent = max(0, min(100, round(score / max_score * 100)))
            score_label = f"{score}/{max_score}"
        cards.append(
            f"""
        <article class="metric-card">
          <div class="metric-card-top">
            <h3>{name}</h3>
            <strong>{html.escape(score_label)}</strong>
          </div>
          <div class="bar" aria-label="{name} score">
            <span style="width: {percent}%"></span>
          </div>
          <p>{explanation}</p>
        </article>"""
        )
    return "\n".join(cards)


def render_rows(rows: list[dict], columns: list[tuple[str, str]], status_key: str | None = None) -> str:
    if not rows:
        return '<p class="empty-state">未提供資料。</p>'

    header = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    body_rows = []
    for row in rows:
        cells = []
        for key, _ in columns:
            value = str(row.get(key, ""))
            if key == status_key:
                cells.append(
                    f'<td><span class="status-pill {status_class(value)}">{html.escape(value or "未標示")}</span></td>'
                )
            else:
                cells.append(f"<td>{html.escape(value)}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
      <div class="table-wrap">
        <table>
          <thead><tr>{header}</tr></thead>
          <tbody>{''.join(body_rows)}</tbody>
        </table>
      </div>"""


def render_evaluation_dashboard(evaluation: str) -> str:
    parsed = parse_evaluation(evaluation)
    if not parsed:
        return ""

    score = parsed.get("score")
    level = html.escape(str(parsed.get("level", "N/A")))
    judgement = html.escape(str(parsed.get("judgement", "")))
    raw = html.escape(str(parsed.get("raw", evaluation)))
    score_label = f"{score}/100" if isinstance(score, int) else "N/A"
    gauge_value = score if isinstance(score, int) else 0

    return f"""
    <section class="evaluation-dashboard">
      <div class="dashboard-heading">
        <div>
          <h2>進度評估儀表板</h2>
          <p>{judgement or "請檢視分項評分與扣分註記。"}</p>
        </div>
        <div class="score-gauge" style="--score: {gauge_value};">
          <span>{html.escape(score_label)}</span>
          <strong>{level}</strong>
        </div>
      </div>

      <div class="metric-grid">
        {render_dimension_cards(parsed.get("dimensions", []))}
      </div>

      <div class="dashboard-section">
        <h3>與上次更新比較</h3>
        {render_rows(
            parsed.get("last_week_comparison", []),
            [("上次下週計畫", "上次下週計畫"), ("本次對應內容", "本次對應內容"), ("狀態", "狀態"), ("說明", "說明")],
            "狀態",
        )}
      </div>

      <div class="dashboard-section">
        <h3>與里程碑比較</h3>
        {render_rows(
            parsed.get("milestone_comparison", []),
            [("里程碑", "里程碑"), ("本次相關進度", "本次相關進度"), ("狀態", "狀態"), ("說明", "說明")],
            "狀態",
        )}
      </div>

      <div class="dashboard-section">
        <h3>資訊不足與扣分註記</h3>
        {render_rows(
            parsed.get("deductions", []),
            [("項目", "項目"), ("影響維度", "影響維度"), ("扣分原因", "扣分原因")],
        )}
      </div>

      <details class="raw-evaluation">
        <summary>查看原始評估資料</summary>
        <pre>{raw}</pre>
      </details>
    </section>"""


def render_page(message=None, error=None, posted=False, content_value=None):
    task_name = html.escape(TASK_NAME)
    content = html.escape(DEFAULT_CONTENT if content_value is None else content_value)
    evaluation_html = render_evaluation_dashboard(DEFAULT_EVALUATION)
    message_html = f'<div class="message success">{html.escape(message)}</div>' if message else ""
    error_html = f'<div class="message error">{html.escape(error)}</div>' if error else ""
    disabled = "disabled" if posted else ""

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ClickUp 更新確認</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif;
      background: #eef2f7;
      color: #172033;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px;
    }}
    main {{
      width: min(880px, 100%);
      background: #ffffff;
      border: 1px solid #d8dee9;
      border-radius: 8px;
      padding: 28px;
      box-shadow: 0 18px 45px rgba(23, 32, 51, 0.12);
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
      line-height: 1.3;
    }}
    p {{
      margin: 0 0 22px;
      color: #596579;
      line-height: 1.6;
    }}
    h2 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.4;
    }}
    label {{
      display: block;
      margin: 18px 0 8px;
      font-weight: 700;
    }}
    input, textarea {{
      width: 100%;
      border: 1px solid #c9d2e0;
      border-radius: 6px;
      font: inherit;
      color: #172033;
      background: #ffffff;
    }}
    input {{
      padding: 11px 12px;
    }}
    textarea {{
      min-height: 300px;
      padding: 12px;
      line-height: 1.6;
      resize: vertical;
      white-space: pre-wrap;
    }}
    .evaluation-dashboard {{
      margin: 18px 0 24px;
      border: 1px solid #c9d2e0;
      border-radius: 8px;
      background: #f8fafc;
      overflow: hidden;
    }}
    .dashboard-heading {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 18px;
      border-bottom: 1px solid #d8dee9;
      background: #ffffff;
    }}
    .dashboard-heading p {{
      margin: 5px 0 0;
      color: #596579;
    }}
    .score-gauge {{
      --score: 0;
      width: 112px;
      height: 112px;
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      border-radius: 50%;
      background: conic-gradient(#2563eb calc(var(--score) * 1%), #e5e7eb 0);
      position: relative;
      color: #172033;
    }}
    .score-gauge::before {{
      content: "";
      position: absolute;
      inset: 10px;
      border-radius: 50%;
      background: #ffffff;
      box-shadow: inset 0 0 0 1px #d8dee9;
    }}
    .score-gauge span,
    .score-gauge strong {{
      position: relative;
      z-index: 1;
    }}
    .score-gauge span {{
      font-weight: 700;
      font-size: 20px;
      line-height: 1;
    }}
    .score-gauge strong {{
      margin-top: 30px;
      position: absolute;
      font-size: 13px;
      color: #596579;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      padding: 16px;
    }}
    .metric-card {{
      border: 1px solid #d8dee9;
      border-radius: 8px;
      background: #ffffff;
      padding: 14px;
    }}
    .metric-card-top {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .metric-card h3,
    .dashboard-section h3 {{
      margin: 0;
      font-size: 15px;
      line-height: 1.4;
    }}
    .metric-card strong {{
      flex: 0 0 auto;
      color: #2563eb;
      font-size: 14px;
    }}
    .metric-card p {{
      margin: 10px 0 0;
      color: #596579;
      font-size: 13px;
      line-height: 1.55;
    }}
    .bar {{
      height: 8px;
      margin-top: 10px;
      overflow: hidden;
      border-radius: 999px;
      background: #e5e7eb;
    }}
    .bar span {{
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, #2563eb, #0f766e);
    }}
    .dashboard-section {{
      padding: 0 16px 16px;
    }}
    .dashboard-section h3 {{
      margin-bottom: 10px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid #d8dee9;
      border-radius: 8px;
      background: #ffffff;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 680px;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #e5e7eb;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
      line-height: 1.5;
    }}
    th {{
      background: #f8fafc;
      color: #596579;
      font-weight: 700;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    .status-pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 9px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .status-good {{
      background: #e8f7ee;
      color: #17633a;
    }}
    .status-watch {{
      background: #fff7d6;
      color: #7a4b00;
    }}
    .status-risk {{
      background: #fff0f0;
      color: #9b1c1c;
    }}
    .status-neutral {{
      background: #e5e7eb;
      color: #374151;
    }}
    .empty-state {{
      margin: 0;
      padding: 12px;
      border: 1px dashed #c9d2e0;
      border-radius: 8px;
      background: #ffffff;
      color: #596579;
      font-size: 13px;
    }}
    .raw-evaluation {{
      margin: 0 16px 16px;
      border: 1px solid #d8dee9;
      border-radius: 8px;
      background: #ffffff;
    }}
    .raw-evaluation summary {{
      cursor: pointer;
      padding: 12px;
      font-weight: 700;
    }}
    pre {{
      margin: 0;
      padding: 14px;
      max-height: 260px;
      overflow: auto;
      white-space: pre-wrap;
      line-height: 1.55;
      font: 13px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      color: #172033;
    }}
    @media (max-width: 720px) {{
      body {{
        padding: 14px;
      }}
      main {{
        padding: 18px;
      }}
      .dashboard-heading {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .metric-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    .actions {{
      display: flex;
      justify-content: flex-end;
      gap: 10px;
      margin-top: 22px;
    }}
    button {{
      border: 0;
      border-radius: 6px;
      padding: 11px 18px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    button[type="button"] {{
      background: #e5e7eb;
      color: #172033;
    }}
    button[type="submit"] {{
      background: #2563eb;
      color: #ffffff;
    }}
    button:disabled {{
      cursor: not-allowed;
      opacity: 0.55;
    }}
    .message {{
      margin: 18px 0;
      padding: 12px 14px;
      border-radius: 6px;
      line-height: 1.5;
    }}
    .success {{
      background: #e8f7ee;
      color: #17633a;
      border: 1px solid #b9e5c8;
    }}
    .error {{
      background: #fff0f0;
      color: #9b1c1c;
      border: 1px solid #f3b6b6;
    }}
  </style>
</head>
<body>
  <main>
    <h1>ClickUp 更新確認</h1>
    <p>請確認更新內容。只有按下「確認更新」後，程式才會送出至 ClickUp。</p>
    {message_html}
    {error_html}
    {evaluation_html}
    <form method="post" action="/submit">
      <input type="hidden" name="confirm_token" value="{CONFIRM_TOKEN}">
      <label for="task_name">要更新的專案</label>
      <input id="task_name" value="{task_name}" readonly>
      <label for="content">更新內容</label>
      <textarea id="content" name="content" {disabled}>{content}</textarea>
      <div class="actions">
        <button type="button" onclick="window.close()">取消</button>
        <button type="submit" {disabled}>確認更新</button>
      </div>
    </form>
  </main>
</body>
</html>"""


@app.get("/")
def index():
    return render_page()


@app.post("/submit")
def submit():
    if request.form.get("confirm_token") != CONFIRM_TOKEN:
        return render_page(error="確認權杖不正確，請回到原確認頁重新送出。"), 403

    content = request.form.get("content", "").strip()
    if not content:
        return render_page(error="更新內容不可為空。", content_value=content), 400

    try:
        update_clickup(content)
    except requests.HTTPError as e:
        detail = e.response.text if e.response is not None else str(e)
        status = e.response.status_code if e.response is not None else "HTTP"
        return render_page(error=f"更新失敗：{status}\n\n{detail}", content_value=content), 502
    except Exception as e:
        return render_page(error=f"更新失敗：{e}", content_value=content), 500

    threading.Timer(1.0, shutdown_server).start()
    return render_page(message="ClickUp 更新成功，可以關閉此頁面。", posted=True, content_value=content)


def shutdown_server():
    if server:
        server.shutdown()


def main():
    global server

    if args.host != "127.0.0.1":
        raise SystemExit("基於安全考量，確認頁只能綁定 127.0.0.1。")

    server = make_server(args.host, args.port, app)
    url = f"http://{args.host}:{args.port}/"
    print(f"ClickUp 更新確認頁已啟動：{url}")
    print("請在瀏覽器確認內容並點擊「確認更新」。")
    webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
