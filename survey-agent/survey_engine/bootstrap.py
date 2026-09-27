# ==============================================================================
# survey_engine/bootstrap.py
# Loads task-sized part files into one shared namespace so every original
# function remains callable without circular imports.
# ==============================================================================

from __future__ import annotations

from pathlib import Path
from typing import Any

PART_FILES: tuple[str, ...] = (
    "00_config.py",
    "01_changelog.py",
    "02_runtime.py",
    "03_labels.py",
    "04_rank_likert.py",
    "05_kb_match.py",
    "06_learning.py",
    "07_vlm.py",
    "08_landing.py",
    "09_county.py",
    "10_children.py",
    "11_carousel.py",
    "12_maxdiff_selectall.py",
    "12b_select_n.py",
    "13_select_one.py",
    "14_matrix.py",
    "15_progression.py",
    "16_inspect.py",
    "17_human.py",
    "18_checks_a.py",
    "19_checks_b.py",
    "20_text_fields.py",
    "20a_form_controls.py",
    "20b_screen_objects.py",
    "20c_question_flow.py",
    "20e_screen_semantics.py",
    "20d_required_gate.py",
    "20f_answer_transaction.py",
    "20g_interaction_contract.py",
    "20h_underline_inputs.py",
    "21_open_text.py",
    "22_execute.py",
    "22a_recovery.py",
    "23_checks_c.py",
    "23b_notice_checks.py",
    "24_preflight.py",
    "25_runner.py",
    "26_reason.py",
    "27_six_step.py",
)

PARTS_DIR = Path(__file__).resolve().parent / "parts"


def load_engine(namespace: dict[str, Any]) -> dict[str, Any]:
    """Exec every part into *namespace* (normally survey_with_salad.globals())."""
    namespace.setdefault("__package__", "survey_engine")
    for name in PART_FILES:
        path = PARTS_DIR / name
        if not path.exists():
            raise FileNotFoundError(
                f"Missing engine part: {path}. Copy the whole survey_engine folder "
                f"next to survey_with_salad.py (including parts/{name})."
            )
        source = path.read_text(encoding="utf-8")
        if source.count("\n") > 800:
            raise RuntimeError(f"{name} exceeds 800 lines ({source.count(chr(10))}).")
        code = compile(source, str(path), "exec")
        exec(code, namespace)
    if not callable(namespace.get("main")):
        raise RuntimeError(
            "survey_engine loaded but main() is missing. "
            "Ensure survey_engine/parts/25_runner.py is present."
        )
    return namespace
