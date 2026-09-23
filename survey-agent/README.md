# Survey automation · v24.0.134

Install the open-source dependencies with `pip install -r requirements.txt`, then run `python survey_with_salad.py` from this directory.

The engine now fuses UIAutomator bounds with OCR coordinates into one confidence-scored form map. Composite Date of Birth screens are resolved as one fact: the agent reads `date_of_birth` from `knowledge_base.json` or `persona_data.py`; if absent, it asks in the terminal for `DD Month YYYY`, persists the declared value, selects Day/Month/Year, verifies all three controls, and taps the right-arrow/Continue control. It never derives DOB from age.

The screenshot scene graph fuses UIAutomator semantics, Tesseract text boxes, OpenCV colored components and contour geometry into exact control bounds for buttons, inputs, dropdown/list boxes and choices. v24.0.134 adds a required-field state machine: a visible validation banner locks Arrow/Continue/Next/Submit, survives when scrolling moves the banner off-screen, scrolls until complete answer cards are visible, and lets the vision model choose a grounded answer. Selection and navigation execute as separate verified steps. Footer success now requires the prior question to disappear or change, so a viewport shift cannot train the RL policy as successful progression. Set `SAVE_SCREEN_MAPS=true` (the default) to keep only `_screen_map_latest.png` and `_screen_map_latest.json` as the current graphical object map.

Copy the stable `survey_with_salad.py` entry point and the complete `survey_engine\` folder.
