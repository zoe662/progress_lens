---
name: progress-updater
description: Update ClickUp project progress comments from user-provided weekly status. Use when the user asks to update, post, or prepare ClickUp progress for an ODA project, including matching a project name to a ClickUp task, formatting this week's progress and next week's plan, and posting the final comment after confirmation.
---

# ClickUp Progress Update

Prepare project progress updates according to fixed rules, confirm the final draft, and then post it as a ClickUp task comment.

## Required Resources

- Task list: `assets/projects_list.csv`
- Last week progress cache: `assets/last_week_progress.csv`
- Update rules: `references/update-rules.md`
- Evaluation rules: `references/evaluation-rules.md`
- Download task list script: `scripts/download_project_list.py`
- Download last week progress script: `scripts/download_last_week_progress.py`
- Configure ClickUp environment script: `scripts/configure_clickup_env.py`
- Post comment script: `scripts/update_clickup_comment.py`
- Python dependencies: `requirements.txt`

## Workflow

1. Read `references/update-rules.md` before asking for progress content.
2. Ensure `assets/projects_list.csv` exists. If it is missing or the requested task cannot be found, run:

```bash
python3 skills/progress-updater/scripts/download_project_list.py
```

After running `scripts/download_project_list.py`, immediately download the latest ClickUp comment cache:

```bash
python3 skills/progress-updater/scripts/download_last_week_progress.py
```

3. Ensure `assets/last_week_progress.csv` exists. If it is missing after the task list refresh, run `scripts/download_last_week_progress.py`.
4. Match the user's project name against `assets/projects_list.csv`.
   - Do not ask the user for a ClickUp task ID.
   - If no task matches, ask the user to confirm the project name.
   - If multiple tasks match, list all matching task names and ask the user to choose one.
   - Continue only after exactly one task is selected.
5. Collect only the fields required by `references/update-rules.md`.
   - Do not ask for the date; use the local date.
   - Do not invent missing progress details.
   - If information is insufficient or does not satisfy `references/update-rules.md`, ask at most three concise follow-up questions per reply.
   - When asking follow-up questions, output only the questions as a short numbered list. Do not add explanations, evaluation notes, praise, summaries, or extra context.
   - Continue asking follow-up questions until the update satisfies the rules or the user explicitly says to stop, end, use the current information, or not provide more details.
   - If the user stops before all details are complete, prepare the update from the available information without inventing missing content, and let the evaluation record the gaps and deductions.
6. Format the final comment exactly according to `references/update-rules.md`.
7. Before posting, read `references/evaluation-rules.md` and evaluate the final prepared update against:
   - the selected project's latest row in `assets/last_week_progress.csv`
   - the selected project's `text_content` milestones in `assets/projects_list.csv`
   - the final prepared comment content
   This evaluation is a scoring step only. Do not ask follow-up questions during evaluation. If information is missing, assign the score according to `evaluation-rules.md` and note the deduction.
8. Write the evaluation JSON directly to a local file. Do not print or paste the evaluation JSON in the conversation. Use a temporary file path such as `/tmp/progress-updater-evaluation-{task-id}.json`, and make the file content exactly match the JSON format defined in `evaluation-rules.md` so the confirmation page can render a dashboard.
9. Show only the final task name and comment content in the conversation. Do not include the evaluation result in the chat response.
10. Immediately run the local browser confirmation script and pass the evaluation file with `--evaluation-file`:

```bash
python3 skills/progress-updater/scripts/update_clickup_comment.py \
  --task-id "{task-id}" \
  --task-name "{task-name}" \
  --content "{content}" \
  --evaluation-file "/tmp/progress-updater-evaluation-{task-id}.json"
```

The script starts a Flask confirmation page bound to `127.0.0.1` and opens it in the user's browser. The page reads the evaluation file and displays the evaluation result as a dashboard above the editable update content, including the total score, dimension score bars, comparison tables, and deduction notes. This local page is the required confirmation step. Do not bypass it. The final ClickUp API request must only be sent after the user reviews the local page and clicks the confirmation button. Do not add or use a headless/direct-post option.

## Environment

Use Python 3. Create a virtual environment and install the required Python packages before running the scripts:

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r skills/progress-updater/requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r skills/progress-updater/requirements.txt
```

Required environment variables:

```bash
export CLICKUP_TOKEN="your-clickup-token"
export CLICKUP_LIST_ID="your-clickup-list-id"
```

`CLICKUP_TOKEN` is required when posting updates. `CLICKUP_LIST_ID` is only required when refreshing `assets/projects_list.csv`.

After the virtual environment is created, use the local browser configuration page to collect and write these values into the virtual environment activation files:

```bash
.venv/bin/python skills/progress-updater/scripts/configure_clickup_env.py --venv .venv
```

On Windows PowerShell, run:

```powershell
.venv\Scripts\python skills/progress-updater/scripts/configure_clickup_env.py --venv .venv
```

The script starts a Flask configuration page at `http://127.0.0.1:8766/` and opens it in the user's browser. The user must type `CLICKUP_TOKEN` and `CLICKUP_LIST_ID` into the local page; do not ask the user to paste secrets into the chat. The page writes the values into existing virtual environment activation files such as `.venv/bin/activate`, `.venv/bin/activate.fish`, `.venv/bin/activate.csh`, `.venv/Scripts/activate.bat`, or `.venv/Scripts/Activate.ps1`. After saving, the user must reactivate the virtual environment so the variables are loaded in the current terminal.

`scripts/update_clickup_comment.py` starts a local Flask confirmation page at `http://127.0.0.1:8765/` and opens it in the user's browser. Run it in a local desktop environment with browser access. The page must stay bound to `127.0.0.1`; do not expose it on `0.0.0.0` or a network interface.
