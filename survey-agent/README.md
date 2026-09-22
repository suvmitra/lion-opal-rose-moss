# Survey automation · v24.0.117

Install the open-source dependencies with `pip install -r requirements.txt`, then run `python survey_with_salad.py` from this directory.

The engine now fuses UIAutomator bounds with OCR coordinates into one confidence-scored form map. Composite Date of Birth screens are resolved as one fact: the agent reads `date_of_birth` from `knowledge_base.json` or `persona_data.py`; if absent, it asks in the terminal for `DD Month YYYY`, persists the declared value, selects Day/Month/Year, verifies all three controls, and taps the right-arrow/Continue control. It never derives DOB from age.

v24.0.117 adds a screenshot scene graph: UIAutomator semantics, Tesseract text boxes, OpenCV colored components and contour geometry are fused into exact control bounds for buttons, inputs, dropdown/list boxes and choices. Action coordinates are re-grounded to the detected object centre, failed retries stay inside that object, and the Android navigation boundary is detected from the current pixels. This removes the fixed Participate clamp that changed the correct y≈900 target to y=875/835. Set `SAVE_SCREEN_MAPS=true` (the default) to keep only `_screen_map_latest.png` and `_screen_map_latest.json` as the current graphical object map.

Copy the stable `survey_with_salad.py` entry point and the complete `survey_engine\` folder.
