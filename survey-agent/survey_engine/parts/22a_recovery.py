# 22a_recovery.py — bounded action recovery


def recover_from_failure(obs: Observation, decision: dict[str, Any], attempt: int) -> Optional[dict[str, Any]]:
    if attempt >= MAX_ACTION_RETRIES:
        return None
    action = str(decision.get("action", "")).lower()
    logger.warning("[RECOVERY] action=%s attempt=%s", action, attempt)
    if action in {"type_text", "type_comment"}:
        return {"action": "wait"}
    if start_gate_visible(obs.ocr_text) and action == "click":
        _START_SESSION["misses"] = int(_START_SESSION.get("misses") or 0) + 1
        logger.warning("[RECOVERY] Start! miss=%s; retarget pill, do not scroll.", _START_SESSION["misses"])
        fill = navigation_cta_decision(obs)
        if fill:
            fill["press_ms"] = 160
            return fill
        return {"action": "wait"}
    if i_agree_consent_visible(obs.ocr_text) and action == "click":
        if i_agree_already_selected(obs) or decision.get("i_agree_continue"):
            _I_AGREE_SESSION["continue_misses"] = int(_I_AGREE_SESSION.get("continue_misses") or 0) + 1
        fill = i_agree_consent_decision(obs)
        if fill:
            logger.warning("[RECOVERY] Consent retarget %s %s", fill.get("target_text"), fill.get("target_coords"))
            return fill
        return {"action": "wait"}
    if action == "click" and ranking_question_visible(obs.ocr_text):
        return {"action": "wait", "postcondition": "screen stable for re-observation", "confidence_score": 0.7}
    if action == "click" and likert_slider_question_visible(obs.ocr_text, obs.ui_nodes):
        used = _LIKERT_SCROLLS.get(question_fingerprint(obs), 0)
        _LIKERT_SCROLLS[question_fingerprint(obs)] = used + 1
        return likert_scroll_decision(obs, likert_missing_names(obs), used)
    if action == "click" and (
        obs.screen_phase in {"survey_landing", "navigation"} or info_page_needs_scroll(obs)
    ) and not ranking_question_visible(obs.ocr_text) and not likert_slider_question_visible(obs.ocr_text, obs.ui_nodes):
        scrolled = scroll_until_cta_decision(obs)
        if scrolled:
            return scrolled
        return {"action": "scroll_down", "postcondition": "screen changed", "confidence_score": 0.9}
    if action in {
        "click", "select_option", "toggle_checkbox", "select_dropdown",
        "select_matrix_cell", "set_slider", "swipe", "drag", "pick_file",
        "handle_permission", "open_date_picker", "open_time_picker", "set_picker_value",
    }:
        return {"action": "wait"}
    return {"action": "wait"}
