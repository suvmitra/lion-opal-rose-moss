# 20f_answer_transaction.py — fresh-question detection and verified answer ownership

_BASE_LOOKS_LIKE_SINGLE_CHOICE = looks_like_single_choice
_BASE_OPTION_LABELS_FROM_OBSERVATION = option_labels_from_observation
_BASE_REQUIRED_ANSWER_MISSING = required_answer_missing
_BASE_OBSERVE_REQUIRED_GATE = observe_required_gate
_BASE_PREFER_PROGRESSION_OVER_REPEAT = prefer_progression_over_repeat
_BASE_SINGLE_CHOICE_RADIO_DECISION = single_choice_radio_decision
_BASE_TEXT_ENTRY_QUESTION_VISIBLE = text_entry_question_visible
_BASE_OBSERVATION_KB_KEY = observation_kb_key


def eircode_sharing_consent_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return bool(
        "eircode" in text
        and ("would you agree" in text or "do you agree" in text)
        and ("share" in text or "kantar media" in text)
    )


def looks_like_single_choice(ocr_text: str) -> bool:
    return bool(
        _BASE_LOOKS_LIKE_SINGLE_CHOICE(ocr_text)
        or eircode_sharing_consent_visible(ocr_text)
    )


def observation_kb_key(obs: Observation) -> str:
    if eircode_sharing_consent_visible(obs.ocr_text):
        return "share_eircode_with_kantar"
    return _BASE_OBSERVATION_KB_KEY(obs)


def option_labels_from_observation(obs: Observation) -> list[str]:
    """Return answer labels only; status, banners and the question are not choices."""
    question = normalized_option_label(current_question_text(obs))
    cleaned: list[str] = []
    for label in _BASE_OPTION_LABELS_FROM_OBSERVATION(obs):
        key = normalized_option_label(label)
        if not key or key == question:
            continue
        if is_chrome_option_label(label) or is_banner_or_instruction_label(label):
            continue
        if is_progression_cta(label) or "next question" in key or key in {"next", "continue", "submit"}:
            continue
        if any(marker in key for marker in (
            "progress bar", "complete survey", "problems with some of the data",
            "questions with errors", "instructions attached",
        )):
            continue
        if len(label) > 180 or label.count("?"):
            continue
        cleaned.append(label)
    return list(dict.fromkeys(cleaned))


def _blank_radio_rows(obs: Observation) -> list[int]:
    """Find the left-hand circular controls exposed as unlabeled accessibility nodes."""
    rows: list[int] = []
    width, height = max(1, obs.image_width), max(1, obs.image_height)
    for node in obs.ui_nodes or []:
        bounds = node.get("bounds") or []
        if len(bounds) != 4 or node_text(node).strip():
            continue
        x1, y1, x2, y2 = [int(value) for value in bounds]
        bw, bh = x2 - x1, y2 - y1
        cy = (y1 + y2) // 2
        if (
            x1 <= width * 0.16 and 0.55 <= bw / max(1, bh) <= 1.65
            and width * 0.025 <= bw <= width * 0.13
            and height * 0.20 <= cy <= height * 0.82
        ):
            rows.append(cy)
    return sorted({int(row) for row in rows})


def visible_radio_choice_question(obs: Observation) -> bool:
    if obs.screen_phase != "survey_question" or information_notice_page(obs):
        return False
    labels = option_labels_from_observation(obs)
    structured = sum(
        bool(node.get("checkable"))
        for node in obs.ui_nodes or []
        if node.get("enabled", True)
    )
    return bool(
        len(labels) >= 2
        and (
            looks_like_single_choice(obs.ocr_text)
            or structured >= 2
            or len(_blank_radio_rows(obs)) >= 2
        )
    )


def actual_answer_selected(obs: Observation, target: str = "") -> bool:
    if target and selected_option_visual(obs, target):
        return True
    if selected_option_labels(obs):
        return True
    return bool(answer_already_selected(obs) or teal_radio_filled(obs))


def question_answer_controls_visible(obs: Observation) -> bool:
    if visible_radio_choice_question(obs):
        return True
    if obs.screen_phase != "survey_question" or information_notice_page(obs):
        return False
    if any(node.get("editable") or node.get("checkable") for node in obs.ui_nodes or []):
        return True
    text = str(obs.ocr_text or "")
    return bool(
        select_all_apply_visible(text) or open_text_question_visible(text)
        or matrix_question(obs) or irish_region_radio_question_visible(text)
        or required_validation_visible(obs)
    )


def observe_required_gate(obs: Observation) -> None:
    """Open a transaction as soon as a fresh unanswered choice appears."""
    _BASE_OBSERVE_REQUIRED_GATE(obs)
    if not visible_radio_choice_question(obs):
        return
    key = required_question_key(obs)
    old = str(_REQUIRED_GATE_SESSION.get("question_key") or "")
    if old and key and not required_same_question(old, key):
        reset_required_gate()
    if actual_answer_selected(obs):
        _REQUIRED_GATE_SESSION.update({
            "active": True, "question_key": key or old,
            "answer_verified": True, "scrolls": 0,
        })
        return
    _REQUIRED_GATE_SESSION.update({
        "active": True, "question_key": key or old,
        "answer_verified": False,
    })


def required_answer_missing(obs: Observation) -> bool:
    if visible_radio_choice_question(obs):
        # An issued/attempted tap is not evidence. Only checked pixels/state count.
        return not actual_answer_selected(obs)
    return _BASE_REQUIRED_ANSWER_MISSING(obs)


def text_entry_question_visible(ocr_text: str, nodes: list[dict[str, Any]]) -> bool:
    if eircode_sharing_consent_visible(ocr_text):
        return False
    return _BASE_TEXT_ENTRY_QUESTION_VISIBLE(ocr_text, nodes)


def prefer_progression_over_repeat(
    decision: dict[str, Any], obs: Observation, stagnation_count: int = 0,
) -> dict[str, Any]:
    """Never turn an unverified option attempt into a footer click."""
    if adult_age_question_visible(obs.ocr_text):
        wanted = adult_age_payload(obs)
        if not adult_age_in_field(obs, wanted):
            field = adult_age_field_coords(obs)
            logger.warning("[AGE INVARIANT] Box is not %s; type it. Next is not an answer.", wanted)
            return {
                "screen_state": "survey_question", "action": "type_text",
                "target_text": "age input field", "target_coords": field,
                "coordinate_authoritative": True, "input_payload": wanted,
                "kb_key": "age", "kb_write": False, "confidence_score": 0.99,
                "postcondition": f"field contains {wanted}",
                "skip_object_grounding": True, "object_kind": "text_input",
                "answer_reason": f"What age are you is a text field. Type stored age {wanted}, then Next.",
            }
    if decision and visible_radio_choice_question(obs):
        action = str(decision.get("action") or "").lower()
        target = str(decision.get("target_text") or "").strip()
        if action in {"click", "select_option", "toggle_checkbox"} and target:
            if not is_progression_cta(target) and not actual_answer_selected(obs, target):
                return decision
    return _BASE_PREFER_PROGRESSION_OVER_REPEAT(decision, obs, stagnation_count)


def single_choice_radio_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Personal sharing consent comes from KB/persona or the terminal operator."""
    if not eircode_sharing_consent_visible(obs.ocr_text):
        return _BASE_SINGLE_CHOICE_RADIO_DECISION(obs)
    stored = configured_multi_option_decision(obs) or exact_kb_option_decision(obs)
    if stored and not is_progression_cta(str(stored.get("target_text") or "")):
        stored["answer_reason"] = "Stored Eircode-sharing consent selected before Continue."
        return stored
    human = capture_human_answer_decision(
        obs,
        "This is a new personal-data consent question. Enter Yes or No before Continue.",
    )
    if human:
        return human
    return {
        "screen_state": "survey_question", "action": "request_human",
        "target_text": None, "confidence_score": 0.99,
        "postcondition": "Eircode-sharing consent supplied",
        "visual_reasoning": (
            "The new Yes/No consent question is unanswered. Continue is locked until "
            "the operator supplies or confirms the personal preference."
        ),
    }


def fresh_question_transaction_regression_self_check() -> bool:
    nodes = [
        {"id": 24, "text": "", "content_desc": "", "bounds": [49, 1325, 136, 1409],
         "clickable": False, "checkable": False, "checked": False, "editable": False, "enabled": True},
        {"id": 25, "text": "Yes, I agree to share my Eircode.", "content_desc": "",
         "bounds": [143, 1336, 850, 1399], "clickable": False, "checkable": False,
         "checked": False, "editable": False, "enabled": True},
        {"id": 28, "text": "", "content_desc": "", "bounds": [49, 1444, 136, 1528],
         "clickable": False, "checkable": False, "checked": False, "editable": False, "enabled": True},
        {"id": 29, "text": "No, I do not agree.", "content_desc": "",
         "bounds": [143, 1455, 542, 1518], "clickable": False, "checkable": False,
         "checked": False, "editable": False, "enabled": True},
        {"id": 30, "text": "Continue", "content_desc": "", "bounds": [0, 1661, 1440, 1812],
         "clickable": True, "checkable": False, "checked": False, "editable": False, "enabled": True},
        {"id": 11, "text": "", "content_desc": "progress bar - 29% complete",
         "bounds": [14, 279, 1428, 328], "clickable": False, "checkable": False,
         "checked": False, "editable": False, "enabled": True},
    ]
    text = (
        "Would you agree to share your Eircode with Kantar Media for that purpose?\n"
        "Yes, I agree to share my Eircode.\nNo, I do not agree.\nContinue"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="eircode-consent",
        ocr_text=text, ui_nodes=nodes,
        kb={"share_eircode_with_kantar": "Yes, I agree to share my Eircode."},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    reset_required_gate()
    stale = required_field_action_guard(obs, {
        "action": "click", "target_text": "Continue", "target_coords": [500, 562],
        "postcondition": "screen changed", "rl_replay": True,
    })
    pick = single_choice_radio_decision(obs)
    labels = option_labels_from_observation(obs)
    typed = configured_text_answer_decision(obs)
    repeated = prefer_progression_over_repeat(dict(pick or {}), obs, stagnation_count=3)
    passed = bool(
        visible_radio_choice_question(obs) and required_answer_missing(obs)
        and stale.get("action") != "click"
        and pick and pick.get("action") == "select_option"
        and "yes" in str(pick.get("target_text") or "").lower()
        and repeated.get("action") == "select_option"
        and typed is None
        and not any("progress bar" in label.lower() for label in labels)
    )
    reset_required_gate()
    if passed:
        logger.info("[SELF-CHECK] Fresh Yes/No question blocks stale Continue until verified.")
    else:
        logger.error("[SELF-CHECK] Fresh-question transaction failed stale=%s pick=%s labels=%s", stale, pick, labels)
    return passed


def age_gender_invariant_regression_self_check() -> bool:
    """Age is typed from KB; Next is not an answer; Female cannot satisfy Male."""
    age_text = "What age are you?\nPlease enter a whole number\n(<) Next question >"
    age = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="age-what",
        ocr_text=age_text, ui_nodes=[], kb={"age": 44, "gender": "Male"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    stale = prefer_progression_over_repeat({
        "action": "click", "target_text": "Next question", "target_coords": [740, 903],
        "rl_replay": True, "postcondition": "screen changed",
    }, age, 3)
    guarded = required_field_action_guard(age, {
        "action": "select_option", "target_text": "(<) Next question >",
        "input_payload": "(<) Next question >", "kb_key": "gender",
    })
    gender_nodes = [
        {"id": 1, "text": "Female", "content_desc": "", "bounds": [80, 900, 900, 1040],
         "clickable": True, "checkable": True, "checked": True, "editable": False, "enabled": True, "selected": True},
        {"id": 2, "text": "Male", "content_desc": "", "bounds": [80, 700, 900, 840],
         "clickable": True, "checkable": True, "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    gender = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="gender",
        ocr_text="What is your gender?\nMale\nFemale\nGender Fluid\nOther\nNext question",
        ui_nodes=gender_nodes, kb={"gender": "Male"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    choice = gender_screen_decision(gender)
    labels = option_labels_from_observation(age)
    passed = bool(
        adult_age_question_visible(age_text)
        and not looks_like_single_choice(age_text)
        and stale.get("action") == "type_text"
        and str(stale.get("input_payload")) == "44"
        and guarded.get("action") == "type_text"
        and choice and choice.get("action") == "select_option"
        and str(choice.get("target_text")).lower() == "male"
        and not any("next" in lab.lower() for lab in labels)
    )
    if passed:
        logger.info("[SELF-CHECK] Age types 44; Next is not an answer; Female cannot replace Male.")
    else:
        logger.error("[SELF-CHECK] Age/gender invariant failed stale=%s guard=%s choice=%s labels=%s",
                     stale, guarded, choice, labels)
    return passed
