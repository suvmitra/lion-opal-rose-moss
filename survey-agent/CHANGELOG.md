# Survey automation changelog

## 24.0.116

- Added a reusable UIAutomator + OCR form-control map with absolute bounds, tap centres, normalized coordinates, grid cells, source and confidence.
- Added a composite DOB master workflow: exact KB/persona lookup, formatted terminal fallback, persistent declared learning, bounded dropdown operation, visual verification, and submit-arrow action.
- Added a startup regression check for DOB parsing, mapping, and routing. No DOB is inferred from age.

- v24.0.54 archived at `archive/survey_with_salad.v24.0.54.py`

## 24.0.55

- Local → Gemini Flash-Lite → one Flash retry → Salad spare.
- Gemini spend capped at $0.30/hour. Salad 503 never blocks a survey.

## 24.0.54

- Salad 503 does not abort startup.
