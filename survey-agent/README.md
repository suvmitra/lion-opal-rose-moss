# Survey automation · v24.0.137

Install the open-source dependencies with `pip install -r requirements.txt`, then run `python survey_with_salad.py` from this directory.

The engine now fuses UIAutomator bounds with OCR coordinates into one confidence-scored form map. Composite Date of Birth screens are resolved as one fact: the agent reads `date_of_birth` from `knowledge_base.json` or `persona_data.py`; if absent, it asks in the terminal for `DD Month YYYY`, persists the declared value, selects Day/Month/Year, verifies all three controls, and taps the right-arrow/Continue control. It never derives DOB from age.

The screenshot scene graph fuses UIAutomator semantics, Tesseract text boxes, OpenCV colored components and contour geometry into exact control bounds for buttons, inputs, dropdown/list boxes and choices. v24.0.137 distinguishes prose disclosures from answer forms, so an Eircode/privacy notice can advance through its real Continue button without being blocked as an unanswered question. Exact option matching and row-level selected-state verification prevent `Dublin` from matching `Rest of Leinster (excluding Dublin)`. Paragraph glyphs are excluded from the interactive graph, and terminal navigation commands are never saved as personal facts. The per-question transaction still requires the same question to show selected/entered state before Arrow/Continue/Next/Submit can run; an auto-revealed new question resets the transaction. Set `SAVE_SCREEN_MAPS=true` (the default) to keep only `_screen_map_latest.png` and `_screen_map_latest.json` as the current graphical object map.

Copy the stable `survey_with_salad.py` entry point and the complete `survey_engine\` folder.
