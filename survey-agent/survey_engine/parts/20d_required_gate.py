# 20d_required_gate.py — non-bypassable required-field and footer validation

_REQUIRED_GATE_SESSION: dict[str, Any] = {
    "active": False, "question_key": "", "answer_verified": False, "scrolls": 0,
    "selected_target": "",
}


def required_validation_visible(obs: Observation) -> bool:
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    return any(token in text for token in (
        "this question is required", "please select an answer",
        "please fill in this field", "correct any required fields",
        "there was an error on your page", "error on your page",
    ))


def required_question_key(obs: Observation) -> str:
    """Stable question identity across vertical scrolling and transient chrome."""
    text = repair_ocr_i_am(str(obs.ocr_text or ""))
    compact = re.sub(r"\s+", " ", text).strip()
    mark = compact.rfind("?")
    if mark >= 0:
        start = max(compact.rfind(".", 0, mark), compact.rfind("!", 0, mark)) + 1
        candidate = compact[start:mark + 1]
        if len(candidate) > 280:
            candidate = candidate[-280:]
    else:
        candidate = str(current_question_text(obs) or compact[:260])
    tokens = [word for word in re.findall(r"[a-z0-9]+", candidate.lower()) if len(word) > 2]
    ignored = {"survey", "question", "required", "please", "answer", "following"}
    return " ".join(word for word in tokens if word not in ignored)[-220:]


def required_same_question(left: str, right: str) -> bool:
    a, b = set(str(left or "").split()), set(str(right or "").split())
    if not a or not b:
        return False
    return len(a & b) / max(1, min(len(a), len(b))) >= 0.68


def reset_required_gate() -> None:
    _REQUIRED_GATE_SESSION.update({
        "active": False, "question_key": "", "answer_verified": False, "scrolls": 0,
        "selected_target": "",
    })


def question_answer_controls_visible(obs: Observation) -> bool:
    if obs.screen_phase != "survey_question":
        return False
    if information_notice_page(obs):
        return False
    if any(node.get("editable") or node.get("checkable") for node in obs.ui_nodes or []):
        return True
    text = str(obs.ocr_text or "")
    return bool(
        looks_like_single_choice(text) or select_all_apply_visible(text)
        or open_text_question_visible(text) or matrix_question(obs)
        or irish_region_radio_question_visible(text)
        or required_validation_visible(obs)
    )


def register_answer_transaction(obs: Observation, target: str = "") -> None:
    key = required_question_key(obs)
    old = str(_REQUIRED_GATE_SESSION.get("question_key") or "")
    if old and key and not required_same_question(old, key):
        reset_required_gate()
    _REQUIRED_GATE_SESSION.update({
        "active": True, "question_key": key or old, "answer_verified": False,
        "scrolls": 0, "selected_target": str(target or ""),
    })


def observe_required_gate(obs: Observation) -> None:
    """Latch validation across scrolls, where the red banner leaves the viewport."""
    if obs.screen_phase != "survey_question" or information_notice_page(obs):
        reset_required_gate()
        return
    key = required_question_key(obs)
    visible = required_validation_visible(obs)
    old = str(_REQUIRED_GATE_SESSION.get("question_key") or "")
    if visible:
        if old and key and not required_same_question(old, key):
            reset_required_gate()
        _REQUIRED_GATE_SESSION["active"] = True
        _REQUIRED_GATE_SESSION["question_key"] = key or old
        return
    if _REQUIRED_GATE_SESSION.get("active") and old and key and not required_same_question(old, key):
        reset_required_gate()


def required_gate_locked(obs: Observation) -> bool:
    observe_required_gate(obs)
    return bool(
        _REQUIRED_GATE_SESSION.get("active")
        and not _REQUIRED_GATE_SESSION.get("answer_verified")
    )


def required_full_answer_cards(obs: Observation) -> list[dict[str, Any]]:
    """Return full answer cards above the fixed footer; clipped fragments do not count."""
    try:
        scene = build_screen_object_map(obs)
    except Exception:
        return []
    width, height = scene.get("image_size") or [obs.image_width, obs.image_height]
    cards: list[dict[str, Any]] = []
    for item in scene.get("controls") or []:
        bounds = list(item.get("visual_bounds") or item.get("bounds") or [])
        milli = list(item.get("visual_milli") or item.get("milli") or [])
        if len(bounds) != 4 or len(milli) != 2:
            continue
        box_w, box_h = bounds[2] - bounds[0], bounds[3] - bounds[1]
        wide_card = box_w >= int(width * 0.58) and box_h >= int(height * 0.045)
        semantic = item.get("role") in {"choice", "input_or_listbox", "dropdown"}
        if wide_card and semantic and 190 <= int(milli[1]) <= 820:
            cards.append(item)
    return cards


def required_options_need_scroll(obs: Observation) -> bool:
    if len(required_full_answer_cards(obs)) >= 2:
        return False
    checkable = [node for node in obs.ui_nodes if node.get("checkable") and node.get("enabled", True)]
    if len(checkable) >= 2:
        return False
    labels = option_labels_from_observation(obs)
    compact = [label for label in labels if 1 < len(label.split()) <= 10 and len(label) <= 90]
    if looks_like_single_choice(obs.ocr_text) and len(compact) >= 2:
        return False
    return int(_REQUIRED_GATE_SESSION.get("scrolls") or 0) < 3


def required_scroll_decision(obs: Observation) -> dict[str, Any]:
    count = int(_REQUIRED_GATE_SESSION.get("scrolls") or 0) + 1
    _REQUIRED_GATE_SESSION["scrolls"] = count
    logger.warning(
        "[REQUIRED GATE] Answer set is clipped/incomplete; reading the full page before footer (%s/3).",
        count,
    )
    return {
        "screen_state": "survey_question", "action": "scroll_down",
        "target_text": "read all required answer options", "confidence_score": 0.99,
        "postcondition": "required options revealed", "required_gate_scroll": True,
        "answer_reason": "A required question is unanswered and its answer set is not fully visible; scroll the form body before choosing.",
    }


def required_is_progression(decision: dict[str, Any]) -> bool:
    action = str(decision.get("action") or "").lower()
    target = str(decision.get("target_text") or "")
    return bool(
        action in {"select_then_continue", "focus_select_continue"}
        or (action == "click" and is_progression_cta(target))
        or decision.get("flow_master")
    )


def split_required_compound_action(decision: dict[str, Any]) -> dict[str, Any]:
    out = dict(decision)
    out["action"] = "select_option"
    out.pop("continue_coords", None)
    out.pop("tap_points", None)
    out["postcondition"] = "selected option is " + str(out.get("target_text") or "answer")
    out["selection_complete"] = True
    out["required_gate_answer"] = True
    out["answer_reason"] = "Required-field guard split selection from navigation; verify the answer before Continue."
    return out


def focused_required_choice_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Recover from a bad footer proposal with one answer-only vision decision."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return None
    if not planned_vlm_backends():
        return None
    prompt = (
        "You are the answer planner for one REQUIRED Android survey question. "
        "Read the whole screenshot and choose the single visible answer most consistent with the supplied persona/KB. "
        "Do NOT click Arrow, Continue, Next, Submit, footer, header, or instruction text. "
        "Return JSON only with action select_option (or click on the answer card), exact target_text, "
        "target_coords [x,y] in 0..1000, selection_complete true, confidence_score, postcondition, "
        "answer_reason, answer_provenance and source_basis.\n"
        f"PAGE_FLOW={page_flow_prompt(obs)}\n"
        f"PERSONA={json.dumps(obs.persona or {}, ensure_ascii=False)[:1800]}\n"
        f"KB={json.dumps(obs.kb or {}, ensure_ascii=False)[:1800]}\n"
        f"OCR={str(obs.ocr_text or '')[:2600]}"
    )
    compact = "JSON only. Select one answer card. Never navigate or click the footer."
    try:
        raw, backend = call_vlm(prompt, Path(str(obs.screenshot)), compact, prefer_flash=True)
        choice = parse_json_response(raw)
    except Exception as exc:
        logger.warning("[REQUIRED GATE] Focused answer model failed: %s", exc)
        return None
    target = str(choice.get("target_text") or "").strip()
    coords = choice.get("target_coords") or []
    if required_is_progression(choice) or not target:
        logger.warning("[REQUIRED GATE] Rejected focused model navigation target=%r backend=%s", target, backend)
        return None
    if isinstance(coords, list) and len(coords) == 2 and int(coords[1]) >= 835:
        logger.warning("[REQUIRED GATE] Rejected focused model footer coordinate=%s", coords)
        return None
    choice.setdefault("screen_state", "survey_question")
    choice.setdefault("action", "select_option")
    choice.setdefault("confidence_score", 0.88)
    choice.setdefault("postcondition", "selected option is " + target)
    choice["selection_complete"] = True
    choice["required_gate_answer"] = True
    logger.info("[REQUIRED GATE] Focused %s selected %r before footer.", backend, target)
    return ground_decision_to_screen_map(choice, obs)


def required_field_action_guard(obs: Observation, decision: dict[str, Any]) -> dict[str, Any]:
    """Final safety barrier: an unanswered required field always owns the next action."""
    if not decision:
        return decision
    if information_notice_page(obs) and required_is_progression(decision):
        reset_required_gate()
        out = dict(decision)
        out["information_notice_progression"] = True
        out["postcondition"] = "information notice advanced"
        logger.info("[REQUIRED GATE] Disclosure page has no answer control; allowing %r.", out.get("target_text"))
        return out
    observe_required_gate(obs)
    action = str(decision.get("action") or "").lower()
    if action in {"select_then_continue", "focus_select_continue"}:
        register_answer_transaction(obs, str(decision.get("target_text") or ""))
        logger.warning("[QUESTION TX] Split compound %s into answer-only selection.", action)
        return split_required_compound_action(decision)
    if action in {"select_option", "toggle_checkbox", "type_text", "type_comment", "set_slider", "select_matrix_cell"}:
        register_answer_transaction(obs, str(decision.get("target_text") or ""))
        out = dict(decision)
        out["question_transaction_answer"] = True
        return out
    if not _REQUIRED_GATE_SESSION.get("active") and required_is_progression(decision) and question_answer_controls_visible(obs):
        register_answer_transaction(obs)
    if not _REQUIRED_GATE_SESSION.get("active"):
        return decision
    if _REQUIRED_GATE_SESSION.get("answer_verified"):
        if required_is_progression(decision):
            out = dict(decision)
            out["required_gate_progression"] = True
            out["postcondition"] = "required question advanced"
            return out
        return decision
    if action in {"scroll_down", "scroll_up"}:
        return decision
    if action == "click" and not required_is_progression(decision):
        return decision
    if required_is_progression(decision):
        if required_options_need_scroll(obs):
            return required_scroll_decision(obs)
        focused = focused_required_choice_decision(obs)
        if focused:
            return focused
        inferred = exact_kb_option_decision(obs) or configured_personal_answer_decision(obs) or inferred_preference_decision(obs)
        if inferred and not required_is_progression(inferred):
            inferred["required_gate_answer"] = True
            logger.warning("[REQUIRED GATE] Replaced footer with grounded answer %r.", inferred.get("target_text"))
            return inferred
        return {
            "screen_state": "survey_question", "action": "request_human",
            "target_text": None, "confidence_score": 0.99,
            "postcondition": "required answer supplied",
            "visual_reasoning": "A required question is visible, but no complete grounded answer could be chosen safely.",
        }
    return decision


def mark_required_gate_answer(before: Observation, after: Observation) -> None:
    if not _REQUIRED_GATE_SESSION.get("active"):
        return
    old = str(_REQUIRED_GATE_SESSION.get("question_key") or required_question_key(before))
    new = required_question_key(after)
    if new and old and not required_same_question(old, new):
        locked = question_answer_controls_visible(after)
        _REQUIRED_GATE_SESSION.update({
            "active": locked, "question_key": new,
            "answer_verified": False, "scrolls": 0, "selected_target": "",
        })
        logger.info(
            "[QUESTION TX] Screen changed after answer; new answer controls=%s.", locked
        )
        return
    _REQUIRED_GATE_SESSION["answer_verified"] = True
    logger.info("[QUESTION TX] Same-question answer verified; footer may be attempted once.")


def required_progression_verified(before: Observation, after: Observation) -> bool:
    """A viewport shift is not progression; the prior question must disappear/change."""
    if after.screen_phase != "survey_question":
        return before.screen_hash != after.screen_hash
    old, new = required_question_key(before), required_question_key(after)
    if old and new and required_same_question(old, new):
        logger.warning("[VERIFY] Required question is still present; viewport/hash change is not progression.")
        return False
    normalized_after = re.sub(r"[^a-z0-9]+", " ", str(after.ocr_text or "").lower())
    old_words = [word for word in old.split() if len(word) >= 4]
    if old_words and sum(word in normalized_after for word in old_words) / len(old_words) >= 0.62:
        logger.warning("[VERIFY] Required question tokens remain visible; footer did not advance.")
        return False
    return before.screen_hash != after.screen_hash


def required_gate_regression_self_check() -> bool:
    base = dict(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="required-top",
        ui_nodes=[], kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    top = Observation(**{**base, "ocr_text": (
        "This question is required. Which of the statements below is closest to your view? "
        "I prefer maximum choice even if this could compromise privacy."
    )})
    lower = Observation(**{**base, "screen_hash": "required-lower", "ocr_text": (
        "Which of the statements below is closest to your view? "
        "I prefer maximum choice. I prefer security and privacy. I am not sure."
    )})
    reset_required_gate()
    first = required_field_action_guard(lower, {
        "action": "select_then_continue", "target_text": "Dublin", "target_coords": [140, 506],
        "continue_coords": [500, 703], "postcondition": "screen changed",
    })
    no_early_footer = first.get("action") == "select_option" and not first.get("continue_coords")
    reset_required_gate()
    blocked = required_field_action_guard(top, {
        "action": "click", "target_text": "Continue »,", "target_coords": [500, 910],
        "postcondition": "screen changed", "confidence_score": 0.92,
    })
    latched = required_gate_locked(lower)
    split = required_field_action_guard(lower, {
        "action": "select_then_continue", "target_text": "I prefer security and privacy.",
        "target_coords": [500, 610], "continue_coords": [500, 910],
    })
    mark_required_gate_answer(lower, lower)
    allowed = required_field_action_guard(lower, {
        "action": "click", "target_text": "next button", "target_coords": [500, 891],
        "flow_master": True, "postcondition": "screen changed",
    })
    unchanged = Observation(**{**base, "screen_hash": "required-shift", "ocr_text": lower.ocr_text})
    passed = bool(
        no_early_footer and blocked.get("action") == "scroll_down" and latched
        and split.get("action") == "select_option" and not split.get("continue_coords")
        and allowed.get("required_gate_progression")
        and not required_progression_verified(lower, unchanged)
    )
    reset_required_gate()
    if passed:
        logger.info("[SELF-CHECK] Required gate scrolls, answers, verifies, then unlocks footer.")
    else:
        logger.error("[SELF-CHECK] Required gate failed blocked=%s split=%s allowed=%s", blocked, split, allowed)
    return passed
