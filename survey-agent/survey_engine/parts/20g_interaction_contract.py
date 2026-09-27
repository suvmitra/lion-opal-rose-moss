# 20g_interaction_contract.py — one non-bypassable contract for answer → verify → navigate

_INTERACTION_CONTRACT: dict[str, Any] = {
    "signature": "",
    "verified": False,
    "verified_target": "",
}

_CONTRACT_EMPTY_MARKERS = (
    "type your answer", "enter your answer", "write your answer", "tap to type",
    "please select", "select one", "choose one", "day", "month", "year",
)


def _contract_body_node(obs: Observation, node: dict[str, Any]) -> bool:
    bounds = node.get("bounds") or []
    if len(bounds) != 4 or node.get("enabled") is False:
        return False
    height = max(1, int(obs.image_height or obs.device_height or 1))
    cy = (int(bounds[1]) + int(bounds[3])) // 2
    return int(height * 0.06) <= cy < int(height * 0.94)


def _contract_node_value(node: dict[str, Any]) -> str:
    value = node_text(node).strip()
    lowered = re.sub(r"\s+", " ", value.lower())
    if not value or any(lowered == marker or lowered.startswith(marker + " ") for marker in _CONTRACT_EMPTY_MARKERS):
        return ""
    return value


def sync_interaction_contract(obs: Observation) -> str:
    """Bind completion evidence to exactly one active question signature."""
    signature = active_question_signature(obs)
    previous = str(_INTERACTION_CONTRACT.get("signature") or "")
    if previous and signature and previous != signature:
        logger.info("[CONTRACT] New question %s -> %s; clearing prior verification.", previous[:70], signature[:70])
        _INTERACTION_CONTRACT.update({
            "signature": signature, "verified": False, "verified_target": "",
        })
    elif signature and not previous:
        _INTERACTION_CONTRACT["signature"] = signature
    return signature


def interaction_contract_state(obs: Observation) -> dict[str, Any]:
    """Normalize screenshot, accessibility and validation evidence into one state."""
    signature = sync_interaction_contract(obs)
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower()).strip()
    body_nodes = [node for node in (obs.ui_nodes or []) if _contract_body_node(obs, node)]
    checkables = [node for node in body_nodes if node.get("checkable")]
    selected = [node for node in checkables if node.get("checked") or node.get("selected")]
    editables = [node for node in body_nodes if node.get("editable")]
    empty_editables = [node for node in editables if not _contract_node_value(node)]
    dropdowns = [
        node for node in body_nodes
        if any(token in (str(node.get("class") or "") + " " + str(node.get("resource_id") or "")).lower()
               for token in ("spinner", "dropdown", "combobox", "select"))
    ]
    empty_dropdowns = [node for node in dropdowns if not _contract_node_value(node)]
    required_error = bool(required_validation_visible(obs))
    information = bool(information_notice_page(obs))
    kind = str((question_type_evidence(obs) or {}).get("kind") or "unknown")
    answer_controls = bool(
        checkables or editables or dropdowns or question_answer_controls_visible(obs)
    )
    question_like = bool(
        "?" in str(current_question_text(obs) or "")
        or any(token in text for token in (
            "please enter", "type your", "select one", "select an answer",
            "choose one", "this question is required", "please fill",
        ))
    )
    multi = bool(
        matrix_question(obs) or select_all_apply_visible(obs.ocr_text)
        or select_up_to_n_visible(obs.ocr_text)
        or ("multi_select_question" in globals() and multi_select_question(obs))
    )

    complete = False
    reason = "unresolved answer control"
    if obs.screen_phase != "survey_question":
        complete, reason = True, "not a survey question"
    elif information:
        complete, reason = True, "information page has no answer control"
    elif adult_age_question_visible(obs.ocr_text):
        complete = adult_age_in_field(obs, adult_age_payload(obs))
        reason = "age is visible" if complete else "age field is empty or incorrect"
    elif birth_date_question_visible(obs.ocr_text):
        value = resolve_birth_date_fact(obs)
        complete = bool(value and birth_date_controls_populated(obs, value))
        reason = "date parts are visible" if complete else "date part is missing"
    elif open_text_question_visible(obs.ocr_text) and (editables or open_text_control_evidence(obs)):
        complete = bool(open_text_box_has_answer(obs))
        reason = "text answer is visible" if complete else "text box is empty"
    elif matrix_question(obs):
        complete = bool(matrix_question_complete(obs))
        reason = "matrix is complete" if complete else "matrix has unanswered rows"
    elif multi:
        complete = bool(
            _INTERACTION_CONTRACT.get("verified")
            and _INTERACTION_CONTRACT.get("signature") == signature
        )
        reason = "multi-answer completion verified" if complete else "multi-answer question is incomplete"
    elif visible_radio_choice_question(obs) or checkables:
        complete = bool(selected or actual_answer_selected(obs))
        reason = "choice is visibly selected" if complete else "no choice is selected"
    elif editables:
        complete = not empty_editables
        reason = "all visible fields contain values" if complete else "visible text field is empty"
    elif dropdowns:
        complete = not empty_dropdowns
        reason = "all visible dropdowns contain values" if complete else "visible dropdown is empty"
    elif not answer_controls and not question_like:
        complete, reason = True, "instruction page has no answer control"
    elif not answer_controls:
        reason = "answer controls are not visible or are below the fold"

    return {
        "signature": signature,
        "kind": kind,
        "answer_controls": answer_controls,
        "checkables": len(checkables),
        "selected": len(selected),
        "editables": len(editables),
        "empty_editables": len(empty_editables),
        "dropdowns": len(dropdowns),
        "empty_dropdowns": len(empty_dropdowns),
        "required_error": required_error,
        "information": information,
        "multi": multi,
        "complete": bool(complete),
        "reason": reason,
    }


def interaction_contract_prompt(obs: Observation) -> str:
    state = interaction_contract_state(obs)
    public = {key: state[key] for key in (
        "signature", "kind", "answer_controls", "checkables", "selected",
        "editables", "empty_editables", "dropdowns", "empty_dropdowns",
        "required_error", "multi", "complete", "reason",
    )}
    public["rule"] = (
        "choose/fill one current answer; navigation is forbidden"
        if not state["complete"]
        else "the current answer is visible; navigation may be proposed"
    )
    return json.dumps(public, ensure_ascii=False, separators=(",", ":"))


def _contract_repair(obs: Observation, state: dict[str, Any]) -> dict[str, Any]:
    """Return one answer action when a router incorrectly proposes navigation."""
    for fn in (
        adult_age_screen_decision,
        birth_date_decision,
        open_text_answer_decision,
        single_choice_radio_decision,
    ):
        try:
            decision = fn(obs)
        except Exception as exc:
            logger.debug("[CONTRACT] %s repair skipped: %s", fn.__name__, exc)
            decision = None
        if decision and not required_is_progression(decision):
            fixed = dict(decision)
            fixed["contract_repair"] = True
            fixed["contract_signature"] = state["signature"]
            return fixed
    try:
        focused = focused_required_choice_decision(obs)
    except Exception as exc:
        logger.debug("[CONTRACT] Focused model repair unavailable: %s", exc)
        focused = None
    if focused and not required_is_progression(focused):
        focused = dict(focused)
        focused["contract_repair"] = True
        focused["contract_signature"] = state["signature"]
        return focused
    if not state["answer_controls"]:
        return {
            "screen_state": "survey_question", "action": "scroll_down",
            "target_text": "find unanswered control", "confidence_score": 0.98,
            "postcondition": "screen changed", "contract_repair": True,
            "contract_signature": state["signature"],
            "answer_reason": state["reason"],
        }
    return {
        "screen_state": "survey_question", "action": "request_human",
        "target_text": None, "confidence_score": 0.99,
        "postcondition": "current answer supplied", "contract_repair": True,
        "contract_signature": state["signature"],
        "visual_reasoning": (
            "Navigation was blocked because " + state["reason"]
            + ". The focused model could not ground a safe answer."
        ),
    }


def enforce_interaction_contract(obs: Observation, decision: dict[str, Any]) -> dict[str, Any]:
    """Final guard: no router, replay or LLM can navigate past an incomplete question."""
    if not isinstance(decision, dict) or obs.screen_phase != "survey_question":
        return decision
    state = interaction_contract_state(obs)
    out = dict(decision)
    out["contract_signature"] = state["signature"]
    if not required_is_progression(out) and not _footer_tap(out):
        return out
    verified_here = bool(
        _INTERACTION_CONTRACT.get("verified")
        and _INTERACTION_CONTRACT.get("signature") == state["signature"]
    )
    if state["complete"] or verified_here:
        out["contract_authorized"] = True
        out["contract_reason"] = state["reason"]
        logger.info("[CONTRACT] Navigation authorized for %s: %s", state["signature"][:80], state["reason"])
        return out
    logger.warning(
        "[CONTRACT] Navigation blocked for %s: %s state=%s",
        state["signature"][:80], state["reason"],
        {key: state[key] for key in ("checkables", "selected", "editables", "empty_editables", "required_error")},
    )
    return _contract_repair(obs, state)


def note_interaction_contract_result(
    before: Observation, after: Observation, decision: dict[str, Any], verified: bool,
) -> None:
    """Remember completion only for the same question and only after visual verification."""
    before_sig = active_question_signature(before)
    after_sig = active_question_signature(after)
    if before_sig != after_sig:
        _INTERACTION_CONTRACT.update({
            "signature": after_sig, "verified": False, "verified_target": "",
        })
        logger.info("[CONTRACT] Dynamic question appeared; it owns the next action.")
        return
    action = str(decision.get("action") or "").lower()
    if not verified or required_is_progression(decision):
        return
    state = interaction_contract_state(after)
    complete_action = bool(
        action in {"type_text", "type_comment", "set_slider", "fill_date_parts"}
        or (action == "select_option" and not state["multi"])
        or bool(decision.get("selection_complete"))
        or (action == "select_matrix_cell" and state["complete"])
    )
    if complete_action and state["complete"]:
        _INTERACTION_CONTRACT.update({
            "signature": before_sig, "verified": True,
            "verified_target": str(decision.get("target_text") or ""),
        })
        logger.info("[CONTRACT] Answer verified for %s; footer may be used on re-observation.", before_sig[:80])


def interaction_contract_regression_self_check() -> bool:
    """A stale completed question cannot unlock Next on a new unanswered question."""
    old = Observation(
        step=0, screenshot=None, image_width=1000, image_height=2000,
        device_width=1000, device_height=2000, screen_hash="old",
        ocr_text="What is your gender?\nMale\nFemale\nNext question",
        ui_nodes=[{
            "id": 1, "text": "Male", "content_desc": "", "class": "RadioButton",
            "resource_id": "", "bounds": [80, 600, 900, 760], "clickable": True,
            "checkable": True, "checked": True, "selected": True, "editable": False,
            "enabled": True,
        }],
        kb={"gender": "Male"}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    new = Observation(
        step=1, screenshot=None, image_width=1000, image_height=2000,
        device_width=1000, device_height=2000, screen_hash="new",
        ocr_text="Which region do you live in?\nConnacht\nDublin\nContinue",
        ui_nodes=[
            {"id": 2, "text": "Connacht", "content_desc": "", "class": "RadioButton",
             "resource_id": "", "bounds": [80, 600, 900, 760], "clickable": True,
             "checkable": True, "checked": False, "selected": False, "editable": False,
             "enabled": True},
            {"id": 3, "text": "Dublin", "content_desc": "", "class": "RadioButton",
             "resource_id": "", "bounds": [80, 800, 900, 960], "clickable": True,
             "checkable": True, "checked": False, "selected": False, "editable": False,
             "enabled": True},
        ],
        kb={"county": "Dublin"}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    selected = Observation(**{**asdict(new), "screen_hash": "selected", "ui_nodes": [
        {**new.ui_nodes[0]}, {**new.ui_nodes[1], "checked": True, "selected": True},
    ]})
    _INTERACTION_CONTRACT.update({
        "signature": active_question_signature(old), "verified": True, "verified_target": "Male",
    })
    blocked = enforce_interaction_contract(new, {
        "action": "click", "target_text": "Continue", "target_coords": [500, 880],
        "confidence_score": 0.99,
    })
    allowed = enforce_interaction_contract(selected, {
        "action": "click", "target_text": "Continue", "target_coords": [500, 880],
        "confidence_score": 0.99,
    })
    passed = bool(
        not required_is_progression(blocked)
        and required_is_progression(allowed)
        and allowed.get("contract_authorized") is True
    )
    _INTERACTION_CONTRACT.update({"signature": "", "verified": False, "verified_target": ""})
    if passed:
        logger.info("[SELF-CHECK] Interaction contract blocks stale Next and allows selected Next.")
    else:
        logger.error("[SELF-CHECK] Interaction contract failed blocked=%s allowed=%s", blocked, allowed)
    return passed
