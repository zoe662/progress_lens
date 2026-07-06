# ClickUp Progress Evaluation Rules

These rules evaluate the quality of the final ClickUp progress update and explain how the current update connects to the previous update and project milestones. This step only scores the prepared update. Do not ask the user follow-up questions during evaluation.

---

## 1. Evaluation Data Sources

| Data | Source | Purpose |
| :--- | :--- | :--- |
| `current_update` | The prepared progress comment | Evaluate content quality and completeness. |
| `last_week_progress` | `assets/last_week_progress.csv` or the previous ClickUp comment | Compare whether the previous `Next Week's Plan` was addressed. |
| `project_milestones` | The `text_content` field in `assets/projects_list.csv`, or user-provided milestone content | Determine whether the update aligns with, leads, or lags milestones. |
| `task_name` / `task_id` | `assets/projects_list.csv` | Confirm that the evaluation targets the correct project. |

If any source is missing, explicitly mark it as `Insufficient Data`. Do not fill gaps, infer milestones, or invent progress.

---

## 2. Total Score and Levels

Each evaluation is scored out of 100 across five dimensions:

| Dimension | Points | Evaluation Focus |
| :--- | ---: | :--- |
| Content Specificity | 25 | Clear outcomes, deliverables, numbers, and impact scope |
| Previous Plan Continuity | 25 | Whether the previous next-week plan is addressed |
| Milestone Alignment | 20 | Whether the update is on track, ahead, or behind milestones |
| Risk and Blocker Transparency | 15 | Whether causes, impacts, and mitigations are disclosed |
| Next Plan Executability | 15 | Whether next steps have clear criteria, owners, or timing |

Score levels:

| Score | Level | Meaning |
| :--- | :--- | :--- |
| 90-100 | A | Complete enough to publish and use for management tracking |
| 80-89 | B | Mostly complete with a few information gaps |
| 70-79 | C | Understandable but missing information; scoring notes must identify gaps |
| 60-69 | D | Significant gaps; difficult to judge actual progress |
| 0-59 | E | Does not meet update requirements and should be rewritten |

---

## 3. Dimension Scoring Rules

### 3.1 Content Specificity (25 points)

- 25 points: Every item has a clear outcome, deliverable, or metric, and completion status is verifiable.
- 18-24 points: Most items are specific, but a few lack numbers, deliverable names, or impact scope.
- 10-17 points: Content is general and shows direction only; completion level is hard to judge.
- 0-9 points: The update uses mostly vague language and actual output cannot be determined.

Deduct points when:

- The update says `in progress`, `under discussion`, `being handled`, or `continuing to move forward` without a concrete state.
- Quantifiable work lacks numbers.
- Qualitative work does not identify a deliverable, decision result, or confirmation party.

### 3.2 Previous Plan Continuity (25 points)

Extract each item from the previous update's `# Next Week's Plan`, then compare each item against the current `# This Week's Progress`.

Mark each item as one of:

- `Completed`: the current update clearly states the result was completed.
- `Partially Completed`: the current update mentions the item, but the completed scope is smaller than planned.
- `Delayed`: the current update states that the item was not completed or was postponed.
- `Canceled`: the current update states that the item was canceled and gives a reason.
- `Scope Changed`: the current update states that the target or deliverable scope changed.
- `Not Addressed`: the current update does not mention the item.

Scoring:

- 25 points: Every previous plan item is clearly addressed, with zero `Not Addressed` items.
- 18-24 points: Most items are addressed, with only one information gap.
- 10-17 points: Only some items are addressed, with multiple unaddressed items.
- 0-9 points: The update barely responds to the previous plan.

`Not Addressed` must not be treated as completed. Deduct points and identify the gap.

### 3.3 Milestone Alignment (20 points)

Compare the current update with project milestones and label the status:

- `On Track`: current outcomes support the nearest milestone being completed on time.
- `Ahead`: current outcomes already complete part or all of a future milestone.
- `Behind`: current outcomes do not meet the milestone that should have been completed.
- `At Risk`: the project is not yet behind, but blockers may affect a milestone.
- `Insufficient Data`: milestone data or current update content is insufficient.

Scoring:

- 20 points: The relationship to the nearest milestone is clear and evidence-backed.
- 14-19 points: Milestone status is mostly clear, but some evidence is missing.
- 7-13 points: The update mentions a milestone but does not explain the relationship.
- 0-6 points: Milestone alignment cannot be determined.

Do not invent milestone dates, tasks, or completion states.

### 3.4 Risk and Blocker Transparency (15 points)

If the current update or milestone comparison indicates risk, the evaluation should look for:

1. Cause
2. Impact scope
3. Schedule or milestone impact
4. Mitigation already taken or planned

Scoring:

- 15 points: Risk is complete and includes mitigation.
- 10-14 points: Risk is described but some impact or mitigation detail is missing.
- 5-9 points: A blocker is mentioned, but impact cannot be judged.
- 0-4 points: A clear risk exists but is not disclosed.

If there is no risk and the content is sufficient to support that conclusion, give full points. If data is insufficient, do not assume there is no risk.

### 3.5 Next Plan Executability (15 points)

Evaluate whether `# Next Week's Plan` is trackable:

- 15 points: Every item includes clear work, completion criteria, collaborator, or expected time.
- 10-14 points: Most items are trackable, but some lack completion criteria.
- 5-9 points: Items show direction only and lack acceptance conditions.
- 0-4 points: The plan is too vague to track next week.

If an item says `continue tracking`, it must specify the tracking target, decision criteria, and expected result. Otherwise, deduct points.

---

## 4. Final Output Format

The evaluation output should be structured JSON by default so `scripts/update_clickup_comment.py` can render it as a dashboard. Every scoring dimension must include a score, max score, and specific explanation.

### 4.1 Default Output: JSON

Output a single JSON object. Do not wrap it in a Markdown code fence. Field names are fixed:

```json
{
  "summary": {
    "total_score": 67,
    "level": "D",
    "judgement": "The update is understandable, but missing API completion counts, test metrics, issue counts, and milestone impact."
  },
  "dimensions": [
    {
      "name": "Content Specificity",
      "score": 14,
      "max_score": 25,
      "explanation": "The update states the main outcomes, but lacks verifiable numbers and deliverable status."
    },
    {
      "name": "Previous Plan Continuity",
      "score": 19,
      "max_score": 25,
      "explanation": "Most previous plan items are addressed, but completion scope is unclear."
    },
    {
      "name": "Milestone Alignment",
      "score": 12,
      "max_score": 20,
      "explanation": "The update is related to milestones, but lacks evidence of milestone completion."
    },
    {
      "name": "Risk and Blocker Transparency",
      "score": 9,
      "max_score": 15,
      "explanation": "Risk is disclosed, but cause, impact, and mitigation deadline are missing."
    },
    {
      "name": "Next Plan Executability",
      "score": 13,
      "max_score": 15,
      "explanation": "The next objective is clear, but completion criteria and confirmation owner are missing."
    }
  ],
  "comparisons": {
    "last_week_plan": [
      {
        "previous_plan": "Complete the remaining API integrations",
        "current_evidence": "Remaining APIs have gradually been integrated",
        "status": "Partially Completed",
        "explanation": "The update does not state whether all APIs were completed."
      }
    ],
    "milestones": [
      {
        "milestone": "2026-07-15: Complete SIT testing",
        "current_evidence": "Testing has started and SIT is planned for next week",
        "status": "At Risk",
        "explanation": "Issues were found during testing, but impact scope is missing."
      }
    ]
  },
  "deductions": [
    {
      "item": "SIT test metrics",
      "affected_dimensions": "Content Specificity, Milestone Alignment",
      "reason": "The update does not provide test case counts, passed counts, failed counts, or tested scope."
    }
  ]
}
```

`summary.total_score` must equal the sum of all `dimensions[].score` values. `summary.level` must follow Section 2. If any comparison table has no data, output an empty array `[]`; do not omit the field.

Dimension explanations must include deduction reasons, verifiable evidence, and missing information. If a dimension cannot be fully scored because of insufficient data, still assign a provisional score and mark the missing data in `explanation`, `comparisons`, or `deductions`. Do not ask follow-up questions during evaluation.

### 4.2 Compatible Output: Markdown Fallback

Use Markdown only if JSON is not possible. The confirmation page will try to parse these sections into a dashboard:

```text
## Evaluation Summary
- Total Score: XX/100 (Level)
- Judgement: One sentence stating whether the update can be published, needs more detail, or should be rewritten

## Dimension Scores
| Dimension | Score | Explanation |
| :--- | ---: | :--- |
| Content Specificity | XX/25 | ... |
| Previous Plan Continuity | XX/25 | ... |
| Milestone Alignment | XX/20 | ... |
| Risk and Blocker Transparency | XX/15 | ... |
| Next Plan Executability | XX/15 | ... |

## Previous Update Comparison
| Previous Plan | Current Evidence | Status | Explanation |
| :--- | :--- | :--- | :--- |

## Milestone Comparison
| Milestone | Current Evidence | Status | Explanation |
| :--- | :--- | :--- | :--- |

## Information Gaps and Deductions
| Item | Affected Dimensions | Reason |
| :--- | :--- | :--- |
```

---

## 5. Information Gap Notes

Include an item in `deductions` when any of the following occurs, and reflect it in the relevant dimension score:

- A previous `# Next Week's Plan` item is not addressed in the current update.
- The current update uses vague wording and completion status cannot be judged.
- The current update may affect a milestone but does not explain the impact.
- Risk exists but lacks cause, impact scope, schedule impact, or mitigation.
- The next-week plan lacks completion criteria, collaborator, or expected time.
- `last_week_progress` or `project_milestones` is missing, preventing comparison.

Each note must identify the missing information and its effect. Do not write only `Insufficient Data`.

---

## 6. Prohibited Actions

- Do not infer that a previous plan item was completed.
- Do not invent milestones, dates, risks, or completion states.
- Do not raise the score because the tone is positive; score only verifiable content.
- Do not ignore unfinished items from the previous update.
- Do not provide only a total score without deduction reasons.
- Do not treat `no risk mentioned` as `no risk`; the content must support the conclusion.
- Do not ask follow-up questions during evaluation. Score only the available content and note gaps.

---

## 7. Evaluation Self-Check

- [ ] Have you obtained the current update?
- [ ] Have you obtained the previous update or `last_week_progress.csv`?
- [ ] Have you obtained project milestones, or marked them as insufficient data?
- [ ] Have you compared each previous `# Next Week's Plan` item?
- [ ] Have you compared the nearest milestones?
- [ ] Have you listed concrete deduction reasons?
- [ ] Have you included every unverifiable item in the deduction notes?
