# ==============================================================================
# File: survey_with_salad.py
# Project: Vision-Led Agentic Mobile Survey Automation
# Version: 24.0.119
#
# Entry point. Implementation is split under survey_engine/parts/ (max 800
# lines each). bootstrap.load_engine binds every original function into this
# module so `python survey_with_salad.py` behaves as before.
# ==============================================================================

from __future__ import annotations

from survey_engine.bootstrap import load_engine

load_engine(globals())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
