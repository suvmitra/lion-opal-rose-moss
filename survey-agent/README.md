# Survey automation · v24.0.133

Install the open-source dependencies with `pip install -r requirements.txt`, then run `python survey_with_salad.py` from this directory.

The engine now fuses UIAutomator bounds with OCR coordinates into one confidence-scored form map. Composite Date of Birth screens are resolved as one fact: the agent reads `date_of_birth` from `knowledge_base.json` or `persona_data.py`; if absent, it asks in the terminal for `DD Month YYYY`, persists the declared value, selects Day/Month/Year, verifies all three controls, and taps the right-arrow/Continue control. It never derives DOB from age.

The screenshot scene graph fuses UIAutomator semantics, Tesseract text boxes, OpenCV colored components and contour geometry into exact control bounds for buttons, inputs, dropdown/list boxes and choices. v24.0.133 adds page-series planning: after every answer the engine compares the active subquestion before and after the tap, waits for WebView JavaScript to reveal the next item, and keeps the fixed footer locked while another required control is visible. Unknown multi-option semantics are sent to the configured vision LLM; the deterministic layer validates its target and prevents early footer submission. Open-text routing now requires a real input object or an unambiguous written-response instruction. Set `SAVE_SCREEN_MAPS=true` (the default) to keep only `_screen_map_latest.png` and `_screen_map_latest.json` as the current graphical object map.

Copy the stable `survey_with_salad.py` entry point and the complete `survey_engine\` folder.
