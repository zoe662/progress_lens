# ClickUp Progress Update Rules

These rules guide the assistant to produce executive-readable project progress updates: the update must show whether meaningful progress was made, whether the schedule is affected, and who owns the next step. The rules also prevent missing information and fabricated details.

---

## 1. Field Definitions

| Field | Source | Rule | Output Example |
| :--- | :--- | :--- | :--- |
| `date` | System | Use the local date automatically in `YYYY/MM/DD` format. Do not ask the user for the date. | `Date: 2026/07/03 update.` |
| `task_name` | User | Must exist in `assets/projects_list.csv` and must map to exactly one task after confirmation. | Internal only; do not show in the report. |
| `task_id` | `assets/projects_list.csv` | Look up from `task_name`. Do not ask the user for it. | Internal only; do not show in the report. |
| `last_week_progress` | User | At least 1 item and at most 3 items. | `# This Week's Progress: {content}` |
| `next_week_plan` | User | At least 1 item and at most 3 items. | `# Next Week's Plan: {content}` |

---

## 2. Content Granularity Rules

### 2.1 Result-Oriented Wording

- Avoid vague wording such as `in progress`, `under discussion`, `being handled`, and `continuing to move forward` unless the item also includes a clear state and outcome.
- Prefer result-oriented wording such as `completed`, `submitted`, `confirmed`, `deployed`, `obtained`, `compiled`, `validated`, and `delivered`.
- If `next_week_plan` uses wording like `continue tracking`, it must specify what will be tracked, the expected completion time, and the decision criteria.

### 2.2 Quantification and Specificity

- If the work is naturally quantifiable, include concrete numbers, such as sample counts, open rates, recall or precision, pass rates, or affected module counts.
- If the work is qualitative, use a clear deliverable name, status, and impact scope instead of inventing numbers.
- Decision rule: quantify when quantification is natural; otherwise state what was done, for whom or which module, and what the result was.

> Anti-fabrication rule: Do not invent dates, numbers, statuses, owners, risk causes, or risk impacts. If the user has not provided enough information, ask a follow-up question. This rule takes priority over the quantification rule.

### 2.3 Risk Description and Severity

If the progress or plan mentions a risk, it must include all of the following:

1. Cause: why the risk exists
2. Impact scope: which module, project, or area is affected
3. Schedule impact: delay duration or affected milestone

Use `[Risk: Low/Medium/High]` only according to these criteria:

| Severity | Criteria |
| :--- | :--- |
| High | The external delivery date or committee reporting schedule is already affected, and no workaround exists. |
| Medium | A single module or internal schedule is affected, but a feasible mitigation or workaround exists. |
| Low | The risk is identified but has not yet affected the schedule, or mitigation is already in progress. |

If the user has not provided enough information to determine severity, ask a follow-up question. Do not default the severity.

### 2.4 Tag Definitions

Each item in the comment template must start with exactly one of these tags:

- `[Risk: Low/Medium/High]`: risk explanation
- `[Milestone]`: external delivery, committee reporting, acceptance, or other major checkpoint
- `[Progress]`: ordinary completed internal work
- `[Pending Confirmation]`: an item that needs another team or manager to confirm before progress can continue; use only in `next_week_plan`

---

## 3. Item Count and Priority

- `last_week_progress` and `next_week_plan` must each contain at least 1 item and at most 3 items. Do not add filler items just to reach 3.
- If user input contains more than 3 items, condense and keep items in this priority order:
  1. Risks or schedule impact
  2. External delivery or committee milestones
  3. Ordinary internal completion items
- If `last_week_progress` includes unfinished work or future plans, move that content to `next_week_plan`. If classification is unclear, ask the user. Do not decide by assumption. Apply the same rule in reverse if `next_week_plan` includes completed work.

---

## 4. Task Matching and Exceptions

- If `task_name` is missing, ask the user for the project name.
- If `assets/projects_list.csv` cannot be read or does not exist, tell the user and stop. Do not generate a task ID from memory or inference.
- If no task matches, ask the user to confirm or rewrite the project name.
- If multiple tasks match, list all matching task names and ask the user to choose one. Do not choose by inference.
- If the matching task is closed or archived, ask the user to confirm whether it should still be updated.

---

## 5. Continuity Check

- Before producing this week's progress, compare each item in the previous ClickUp comment's `next_week_plan` with this update's `last_week_progress`. Mark each item as `Completed`, `Delayed`, `Canceled`, or `Scope Changed`.
- If an item from the previous plan is missing from the user's current input, ask for its status. Do not assume it was completed or omit it.

---

## 6. Pre-Posting Confirmation and Duplicate Handling

- Before posting to ClickUp, show the full draft, including date, this week's progress, and next week's plan, and get explicit user confirmation.
- If an update comment already exists for the same cycle, ask whether to overwrite the existing comment or add a new comment. Do not decide automatically.

---

## 7. Follow-Up Rules

| Situation | Action |
| :--- | :--- |
| `task_name` is missing, unmatched, or ambiguous | Follow Section 4. |
| `last_week_progress` is missing | Ask for specific completed progress from this week. |
| Content is vague, lacks a clear status, lacks numbers, or lacks a deliverable | Ask which specific module or deliverable was completed, what the result was, and whether there are dates, counts, or test results. |
| Risk is mentioned but incomplete | Ask for the missing parts listed in Section 2.3. |
| More than 3 items are provided | Condense according to Section 3. |
| Content crosses this-week and next-week categories | Move it to the correct field; if unclear, ask the user. |
| `next_week_plan` says `continue tracking` without details | Ask what will be tracked, expected completion time, and decision criteria. |
| Any date, number, status, owner, risk cause, or impact is incomplete | Ask a follow-up question. Do not infer or fabricate. |

---

## 8. Pre-Output Self-Check

Before producing the final comment, verify:

- [ ] Date format is `YYYY/MM/DD`.
- [ ] This-week and next-week sections each contain 1 to 3 non-filler items.
- [ ] No vague wording is used without a concrete state or result.
- [ ] Every item has a valid `[Tag]`.
- [ ] Quantifiable items include numbers; qualitative items include clear deliverables and statuses.
- [ ] Risk items include cause, impact scope, schedule impact, and evidence for severity.
- [ ] This week's progress has been checked against last week's next-week plan.
- [ ] The user has confirmed the complete draft.
- [ ] No field was inferred or generated without user-provided evidence.

---

## 9. Comment Template

```text
Date: YYYY/MM/DD update.

# This Week's Progress:
1. [Tag] Concrete outcome: details, including metrics, deliverables, or impact scope
2. ...
3. ...

# Next Week's Plan:
1. [Tag] Concrete action item: expected completion date, collaborator, and completion criteria
2. ...
3. ...
```
