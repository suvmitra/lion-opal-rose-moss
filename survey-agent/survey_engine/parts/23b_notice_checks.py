# 23b_notice_checks.py — disclosure-page and exact-option regressions


def notice_and_exact_option_regression_self_check() -> bool:
    nodes = [
        {"id": 10, "text": "Dublin", "content_desc": "", "bounds": [150, 900, 280, 950],
         "clickable": False, "editable": False, "checkable": False, "enabled": True},
        {"id": 11, "text": "Rest of Leinster (excluding Dublin)", "content_desc": "",
         "bounds": [150, 1100, 900, 1150], "clickable": False, "editable": False,
         "checkable": False, "enabled": True},
    ]
    exact = best_option_text_node(nodes, "Dublin radio")
    text = (
        "We’d like to ask you to share your Eircode with us, so we can assign you to a "
        "geographical region and for coding geodemographic categories. Our suppliers and "
        "partners will not use it for another purpose. We will retain your Eircode for 24 months, "
        "after which it will be deleted. Continue"
    )
    notice_nodes = [{
        "id": 16, "text": "Continue", "content_desc": "", "bounds": [0, 2253, 1440, 2403],
        "clickable": True, "editable": False, "checkable": False, "enabled": True,
    }]
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="eircode-notice-fixture",
        ocr_text=text, ui_nodes=notice_nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    register_answer_transaction(obs, "stale prior answer")
    guarded = required_field_action_guard(obs, {
        "action": "click", "target_text": "Continue", "target_element_id": 16,
        "target_coords": [500, 753], "postcondition": "screen changed",
    })
    passed = bool(
        exact and exact.get("id") == 10
        and information_notice_page(obs)
        and not question_answer_controls_visible(obs)
        and guarded.get("action") == "click"
        and guarded.get("information_notice_progression") is True
        and guarded.get("postcondition") == "information notice advanced"
        and not required_gate_locked(obs)
        and operator_progression_command("Click on Continue button")
    )
    reset_required_gate()
    if passed:
        logger.info("[SELF-CHECK] Exact Dublin and Eircode disclosure Continue checks passed.")
    else:
        logger.error("[SELF-CHECK] Notice/exact-option failed exact=%s guarded=%s", exact, guarded)
    return passed
