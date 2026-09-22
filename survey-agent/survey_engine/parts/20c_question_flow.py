# 20c_question_flow.py — evidence-based question ownership and post-answer navigation


def comfort_question_header_visible(ocr_text: str) -> bool:
    """Recognize the AI-access comfort series even after its option cards collapse."""
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    # Tesseract commonly reads the uppercase I in "AI assistant" as lowercase l.
    ai_assistant = bool(re.search(r"\ba(?:i|l|1)\s+assistant\b", text))
    return bool(
        "how comfortable" in text
        and ai_assistant
        and "access" in text
        and ("phone" in text or "personal information" in text)
    )


def comfort_options_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    hits = sum(option.lower() in text for option in _COMFORT_OPTIONS)
    return hits >= 2


def question_type_evidence(obs: Observation) -> dict[str, Any]:
    """Classify by positive UI evidence; generic wording alone never creates a matrix."""
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    scene = build_screen_object_map(obs) if "build_screen_object_map" in globals() else {"controls": []}
    controls = scene.get("controls") or []
    footer = any(
        item.get("role") == "button"
        and 780 <= int((item.get("visual_milli") or item.get("milli") or [0, 0])[1]) < int(scene.get("navigation_top_milli") or 945)
        for item in controls
        if len(item.get("visual_milli") or item.get("milli") or []) == 2
    )
    evidence = {
        "comfort_header": comfort_question_header_visible(text),
        "comfort_options": comfort_options_visible(text),
        "matrix_instruction": any(term in text for term in (
            "select one for each row", "select one answer per row", "in each row",
            "rate each row", "one answer in every row",
        )),
        "matrix_columns": (
            ("strongly disagree" in text and "strongly agree" in text)
            or ("have never used" in text and "within the past 12 months" in text)
        ),
        "footer_button": footer,
    }
    if evidence["comfort_header"]:
        kind = "comfort_likert"
    elif evidence["matrix_instruction"] or evidence["matrix_columns"]:
        kind = "matrix"
    elif open_text_question_visible(obs.ocr_text):
        kind = "open_text"
    elif looks_like_single_choice(obs.ocr_text):
        kind = "single_choice"
    else:
        kind = "unknown"
    return {"kind": kind, "evidence": evidence}


def mapped_footer_control(obs: Observation) -> Optional[dict[str, Any]]:
    """Return the exact fixed footer CTA, never a question word or Android nav key."""
    try:
        scene = build_screen_object_map(obs)
    except Exception:
        return None
    nav_top = int(scene.get("navigation_top_milli") or 945)
    ranked: list[tuple[float, dict[str, Any]]] = []
    for item in scene.get("controls") or []:
        milli = list(item.get("visual_milli") or item.get("milli") or [])
        if len(milli) != 2 or item.get("role") != "button" or not item.get("enabled", True):
            continue
        x, y = int(milli[0]), int(milli[1])
        if not (250 <= x <= 750 and 760 <= y < nav_top):
            continue
        label = _clean_control_label(item.get("label") or "")
        forbidden = any(word in label for word in ("close", "reload", "privacy", "help", "back"))
        if forbidden:
            continue
        named = any(word in label for word in ("next", "continue", "submit", "proceed", "arrow"))
        colored = item.get("color") in {"purple", "green", "blue", "orange"}
        if not named and not colored:
            continue
        score = float(item.get("confidence") or 0) + (6.0 if named else 0.0)
        score += (2.0 if "uiautomator" in str(item.get("source") or "") else 0.0)
        score += y / 1000.0
        ranked.append((score, item))
    return max(ranked, key=lambda pair: pair[0])[1] if ranked else None


def mapped_footer_progression_decision(
    obs: Observation,
    reason: str = "The answer is verified; use the mapped fixed footer control.",
) -> Optional[dict[str, Any]]:
    control = mapped_footer_control(obs)
    if not control:
        return None
    milli = list(control.get("visual_milli") or control.get("milli") or [])
    bounds = list(control.get("visual_bounds") or control.get("bounds") or [])
    label = str(control.get("label") or "Next").strip() or "Next"
    logger.info("[FLOW MASTER] Verified answer -> footer %r bounds=%s milli=%s", label, bounds, milli)
    return {
        "screen_state": "survey_question", "action": "click",
        "target_text": label, "target_coords": [int(milli[0]), int(milli[1])],
        "target_bounds": bounds, "coordinate_authoritative": True,
        "confidence_score": 0.99, "postcondition": "question advanced",
        "answer_reason": reason, "skip_object_grounding": True,
        "object_kind": "button", "flow_master": True,
    }


def post_answer_flow_decision(
    obs: Observation, pending_question_advance: bool,
) -> Optional[dict[str, Any]]:
    """Navigation owns the screen after a verified answer; stale answer routers cannot pre-empt it."""
    flow = question_type_evidence(obs)
    compact_comfort = bool(
        flow["kind"] == "comfort_likert"
        and not flow["evidence"]["comfort_options"]
        and _COMFORT_SESSION.get("pick_issued")
    )
    if not pending_question_advance and not compact_comfort:
        return None
    decision = mapped_footer_progression_decision(obs)
    if decision:
        if _MATRIX_SESSION.get("active") and flow["kind"] != "matrix":
            reset_matrix_session()
            logger.info("[FLOW MASTER] Cleared stale matrix ownership; current type=%s", flow["kind"])
        return decision
    return None


def question_flow_regression_self_check() -> bool:
    """Fixture for the exact 2026-09-22 compact comfort screen and footer arrow."""
    text = (
        "How comfortable are you/ would you be with an AI assistant having access "
        "to each of the following functions and types of personal information and data on your phone?"
    )
    node = {
        "id": 56, "text": "", "content_desc": "next button",
        "class": "android.widget.Button", "resource_id": "",
        "bounds": [332, 2673, 1106, 2831], "clickable": True,
        "editable": False, "enabled": True, "checkable": False,
    }
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="comfort-compact",
        ocr_text=text, ui_nodes=[node], kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _COMFORT_SESSION.update({"topic": "location", "picked": False, "pick_issued": True})
    flow = question_type_evidence(obs)
    decision = post_answer_flow_decision(obs, True)
    point = (decision or {}).get("target_coords") or [0, 0]
    passed = bool(
        flow["kind"] == "comfort_likert"
        and not matrix_semantic_hint(text)
        and not matrix_grid_visible(obs)
        and decision and decision.get("action") == "click"
        and decision.get("target_text") == "next button"
        and 495 <= int(point[0]) <= 503 and 887 <= int(point[1]) <= 895
        and decision.get("target_bounds") == [332, 2673, 1106, 2831]
    )
    if passed:
        logger.info("[SELF-CHECK] Flow master uses mapped footer [499,891], not stale matrix scrolling.")
    else:
        logger.error("[SELF-CHECK] Flow master failed flow=%s decision=%s", flow, decision)
    return passed
