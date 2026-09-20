# Survey automation · v24.0.17

Vision-led Android survey runner. **v24.0.16 is archived** at
`archive/survey_with_salad.v24.0.16.py` — no prior code was discarded.

## v24.0.17 — terminal key-in

If the model is silent or returns `request_human` on a personal question
(for example *Which of these pets currently live with you in your household?*),
the runner no longer exits.

1. It prints the question and visible options on the terminal.
2. You type `Cat, Dog, Fish`, `only Fish`, `none`, numbered rows, or `skip`.
3. It writes `knowledge_base.json` (`household_pets` plus fallbacks).
4. It ticks each matching checkbox, one cycle at a time, then continues.

Copy **both** files together:

- `survey_with_salad.py`
- `human_answer_matching.py`

Environment:

```
ALLOW_INTERACTIVE_HUMAN_INPUT=true
HUMAN_INPUT_MAX_ATTEMPTS=3
```

Stdin must be a TTY. Non-interactive runs still halt rather than hang.
