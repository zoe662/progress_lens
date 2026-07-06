import argparse
import html
import secrets
import threading
import webbrowser
from pathlib import Path

from flask import Flask, request
from werkzeug.serving import make_server

from clickup_env import read_clickup_env_from_venv


PROJECT_ROOT = Path(__file__).resolve().parents[3]

parser = argparse.ArgumentParser()
parser.add_argument(
    "--venv",
    default=".venv",
    help="Path to the Python virtual environment. Relative paths are resolved from the project root.",
)
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8766)

args = parser.parse_args()

venv_arg = Path(args.venv)
VENV_PATH = venv_arg.resolve() if venv_arg.is_absolute() else (PROJECT_ROOT / venv_arg).resolve()
CONFIRM_TOKEN = secrets.token_urlsafe(32)

app = Flask(__name__)
server = None


def single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def batch_value(value: str) -> str:
    return value.replace("%", "%%")


def replace_block(text: str, start: str, end: str, block: str) -> str:
    start_at = text.find(start)
    end_at = text.find(end, start_at + len(start)) if start_at != -1 else -1

    if start_at != -1 and end_at != -1:
        end_at += len(end)
        text = text[:start_at].rstrip() + "\n\n" + text[end_at:].lstrip()

    return text.rstrip() + "\n\n" + block.rstrip() + "\n"


def write_text(path: Path, content: str):
    path.write_text(content, encoding="utf-8")


def update_activation_file(path: Path, start: str, end: str, block: str):
    current = path.read_text(encoding="utf-8")
    write_text(path, replace_block(current, start, end, block))


def write_clickup_env(clickup_token: str, clickup_list_id: str):
    if not VENV_PATH.exists():
        raise RuntimeError(f"找不到虛擬環境：{VENV_PATH}")
    if any(char in clickup_token + clickup_list_id for char in "\r\n"):
        raise RuntimeError("CLICKUP_TOKEN 和 CLICKUP_LIST_ID 不可包含換行字元。")

    values = {
        "CLICKUP_TOKEN": clickup_token,
        "CLICKUP_LIST_ID": clickup_list_id,
    }
    updated = []

    posix_activate = VENV_PATH / "bin" / "activate"
    if posix_activate.exists():
        start = "# >>> progress-updater clickup env >>>"
        end = "# <<< progress-updater clickup env <<<"
        body = "\n".join(f"export {key}={single_quote(value)}" for key, value in values.items())
        update_activation_file(posix_activate, start, end, f"{start}\n{body}\n{end}")
        updated.append(posix_activate)

    fish_activate = VENV_PATH / "bin" / "activate.fish"
    if fish_activate.exists():
        start = "# >>> progress-updater clickup env >>>"
        end = "# <<< progress-updater clickup env <<<"
        body = "\n".join(f"set -gx {key} {single_quote(value)}" for key, value in values.items())
        update_activation_file(fish_activate, start, end, f"{start}\n{body}\n{end}")
        updated.append(fish_activate)

    csh_activate = VENV_PATH / "bin" / "activate.csh"
    if csh_activate.exists():
        start = "# >>> progress-updater clickup env >>>"
        end = "# <<< progress-updater clickup env <<<"
        body = "\n".join(f"setenv {key} {single_quote(value)}" for key, value in values.items())
        update_activation_file(csh_activate, start, end, f"{start}\n{body}\n{end}")
        updated.append(csh_activate)

    batch_activate = VENV_PATH / "Scripts" / "activate.bat"
    if batch_activate.exists():
        start = "REM >>> progress-updater clickup env >>>"
        end = "REM <<< progress-updater clickup env <<<"
        body = "\n".join(f'set "{key}={batch_value(value)}"' for key, value in values.items())
        update_activation_file(batch_activate, start, end, f"{start}\n{body}\n{end}")
        updated.append(batch_activate)

    powershell_activate = VENV_PATH / "Scripts" / "Activate.ps1"
    if powershell_activate.exists():
        start = "# >>> progress-updater clickup env >>>"
        end = "# <<< progress-updater clickup env <<<"
        body = "\n".join(f"$env:{key} = {powershell_quote(value)}" for key, value in values.items())
        update_activation_file(powershell_activate, start, end, f"{start}\n{body}\n{end}")
        updated.append(powershell_activate)

    if not updated:
        raise RuntimeError(f"找不到可寫入的 activate 檔案：{VENV_PATH}")

    return updated


def read_existing_values() -> dict[str, str]:
    candidates = [
        VENV_PATH / "bin" / "activate",
        VENV_PATH / "Scripts" / "Activate.ps1",
        VENV_PATH / "Scripts" / "activate.bat",
    ]
    return read_clickup_env_from_venv(candidates)


def render_page(message=None, error=None, updated_files=None, posted=False, values=None):
    values = values if values is not None else read_existing_values()
    clickup_token = html.escape(values.get("CLICKUP_TOKEN", ""), quote=True)
    clickup_list_id = html.escape(values.get("CLICKUP_LIST_ID", ""), quote=True)
    message_html = f'<div class="message success">{html.escape(message)}</div>' if message else ""
    error_html = f'<div class="message error">{html.escape(error)}</div>' if error else ""
    files_html = ""

    if updated_files:
        items = "\n".join(f"<li>{html.escape(str(path))}</li>" for path in updated_files)
        files_html = f"<ul>{items}</ul>"

    disabled = "disabled" if posted else ""

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ClickUp 環境變數設定</title>
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
      width: min(760px, 100%);
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
    label {{
      display: block;
      margin: 18px 0 8px;
      font-weight: 700;
    }}
    input {{
      width: 100%;
      border: 1px solid #c9d2e0;
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
      color: #172033;
      background: #ffffff;
    }}
    .hint {{
      margin-top: 8px;
      color: #69758a;
      font-size: 13px;
      line-height: 1.5;
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
      white-space: pre-wrap;
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
    ul {{
      margin: 10px 0 0;
      padding-left: 20px;
      color: #596579;
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
  <main>
    <h1>ClickUp 環境變數設定</h1>
    <p>請輸入 ClickUp 設定值。送出後會寫入虛擬環境的 activate 檔案。</p>
    {message_html}
    {error_html}
    {files_html}
    <form method="post" action="/submit">
      <input type="hidden" name="confirm_token" value="{CONFIRM_TOKEN}">
      <label for="clickup_token">CLICKUP_TOKEN</label>
      <input id="clickup_token" name="clickup_token" type="password" autocomplete="off" value="{clickup_token}" required {disabled}>
      <div class="hint">Token 只會寫入本機設定檔，不會顯示在終端機輸出。</div>
      <label for="clickup_list_id">CLICKUP_LIST_ID</label>
      <input id="clickup_list_id" name="clickup_list_id" autocomplete="off" value="{clickup_list_id}" required {disabled}>
      <div class="actions">
        <button type="button" onclick="window.close()">取消</button>
        <button type="submit" {disabled}>儲存設定</button>
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
        return render_page(error="確認權杖不正確，請回到原設定頁重新送出。"), 403

    clickup_token = request.form.get("clickup_token", "").strip()
    clickup_list_id = request.form.get("clickup_list_id", "").strip()

    if not clickup_token or not clickup_list_id:
        return render_page(
            error="CLICKUP_TOKEN 和 CLICKUP_LIST_ID 都必須填寫。",
            values={"CLICKUP_TOKEN": clickup_token, "CLICKUP_LIST_ID": clickup_list_id},
        ), 400

    try:
        updated_files = write_clickup_env(clickup_token, clickup_list_id)
    except Exception as e:
        return render_page(
            error=f"設定失敗：{e}",
            values={"CLICKUP_TOKEN": clickup_token, "CLICKUP_LIST_ID": clickup_list_id},
        ), 500

    threading.Timer(1.0, shutdown_server).start()
    return render_page(
        message="設定已寫入。請重新啟用虛擬環境，讓目前終端機載入新的環境變數。",
        updated_files=updated_files,
        posted=True,
        values={"CLICKUP_TOKEN": clickup_token, "CLICKUP_LIST_ID": clickup_list_id},
    )


def shutdown_server():
    if server:
        server.shutdown()


def main():
    global server

    if args.host != "127.0.0.1":
        raise SystemExit("基於安全考量，設定頁只能綁定 127.0.0.1。")

    server = make_server(args.host, args.port, app)
    url = f"http://{args.host}:{args.port}/"
    print(f"ClickUp 環境變數設定頁已啟動：{url}")
    print("請在瀏覽器輸入設定值並點擊「儲存設定」。")
    webbrowser.open(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
