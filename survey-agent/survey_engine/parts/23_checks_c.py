# 23_checks_c.py — shared engine namespace (do not import directly)



# ------------------------------------------------------------------------------
# Preflight
# ------------------------------------------------------------------------------

def navigation_regression_self_check() -> bool:
    """Guard the dashboard routing behavior that regressed in v24.0.5."""
    sample_nodes = [
        {"id": 1, "text": "Featured Surveys", "content_desc": "", "bounds": [60, 900, 400, 960],
         "clickable": False, "checkable": False, "checked": False, "editable": False,
         "enabled": True, "focusable": False, "selected": False},
        {"id": 2, "text": "5 min", "content_desc": "", "bounds": [220, 1100, 340, 1160],
         "clickable": False, "checkable": False, "checked": False, "editable": False,
         "enabled": True, "focusable": False, "selected": False},
        {"id": 3, "text": "€0.29", "content_desc": "", "bounds": [210, 1210, 350, 1280],
         "clickable": False, "checkable": False, "checked": False, "editable": False,
         "enabled": True, "focusable": False, "selected": False},
        {"id": 4, "text": "6 min", "content_desc": "", "bounds": [850, 1100, 970, 1160],
         "clickable": False, "checkable": False, "checked": False, "editable": False,
         "enabled": True, "focusable": False, "selected": False},
        {"id": 5, "text": "€0.81", "content_desc": "", "bounds": [840, 1210, 980, 1280],
         "clickable": False, "checkable": False, "checked": False, "editable": False,
         "enabled": True, "focusable": False, "selected": False},
    ]
    phase = classify_screen_phase("Best Games My Games Featured Surveys", sample_nodes)
    tiles = extract_survey_tiles(sample_nodes, 1440, 3088)
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="self-check",
        ocr_text="Best Games My Games Featured Surveys", ui_nodes=sample_nodes,
        kb={}, persona={}, screen_phase=phase, survey_tiles=tiles,
    )
    bad_memory_action = {
        "action": "click", "question_text": "What types of flights do you take?",
        "kb_key": "flight_types", "target_element_id": None,
        "target_text": None, "target_coords": None, "confidence_score": 0.72,
    }
    repaired = repair_decision_for_screen(bad_memory_action, observation, quiet=True)
    failing_run_ocr = """Balance: €0.16 €0.16 / €5.00 Cashout
Best Garnes My Garnes
You haven't started any Games yet Explore Games and start earning!
5 min €0.29 6 min €0.81
Earn Surveys Games Account"""
    recovered_phase = classify_screen_phase(failing_run_ocr, sample_nodes[1:])
    recovered_observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="failing-run-fixture",
        ocr_text=failing_run_ocr, ui_nodes=sample_nodes[1:], kb={}, persona={},
        screen_phase=recovered_phase, survey_tiles=tiles,
    )
    hallucinated_balance_action = {
        "action": "click", "question_text": "What is the balance?",
        "target_element_id": 11, "target_text": "Balance:",
        "target_coords": [105, 202, 280, 258], "confidence_score": 1.0,
    }
    recovered_decision = repair_decision_for_screen(
        hallucinated_balance_action, recovered_observation, quiet=True
    )
    stale_overlay_phase = classify_screen_phase(
        "Qualification Just a few questions before the survey When you fly?",
        sample_nodes,
    )
    catalog_ocr = """Balance: €0.16 €0.16 / €5.00
Best Match Short Surveys Highest Payout
3 min 6 min €0.05 €0.22
7 min 8 min €0.19 €0.22
8 min 10 min €0.20 €0.22
10 min 10 min €0.39 €0.15
Earn Surveys Games Account"""
    catalog_nodes = [
        {**sample_nodes[0], "id": 20, "text": "Best Match Short Surveys Highest Payout",
         "bounds": [100, 680, 1340, 820]},
        {**sample_nodes[1], "id": 21, "text": "3 min", "bounds": [300, 900, 420, 970]},
        {**sample_nodes[2], "id": 22, "text": "€0.05", "bounds": [285, 1030, 430, 1110]},
        {**sample_nodes[3], "id": 23, "text": "6 min", "bounds": [920, 900, 1040, 970]},
        {**sample_nodes[4], "id": 24, "text": "€0.22", "bounds": [905, 1030, 1050, 1110]},
    ]
    catalog_phase = classify_screen_phase(catalog_ocr, catalog_nodes)
    catalog_tiles = extract_survey_tiles(catalog_nodes, 1440, 3088)
    catalog_observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="survey-catalog-fixture",
        ocr_text=catalog_ocr, ui_nodes=catalog_nodes, kb={}, persona={},
        screen_phase=catalog_phase, survey_tiles=catalog_tiles,
    )
    catalog_decision = repair_decision_for_screen({
        "action": "click", "question_text": "Select a survey to complete.",
        "target_element_id": 12, "target_text": "€0.16",
        "target_coords": [105, 265, 266, 345], "confidence_score": 0.0,
    }, catalog_observation, quiet=True)
    catalog_coords = catalog_decision.get("target_coords") or []
    catalog_x = int(catalog_coords[0] * 1440 / 1000) if len(catalog_coords) == 2 else -1
    catalog_y = int(catalog_coords[1] * 3088 / 1000) if len(catalog_coords) == 2 else -1
    catalog_tap_inside_card = any(
        tile["bounds"][0] <= catalog_x <= tile["bounds"][2]
        and tile["bounds"][1] <= catalog_y <= tile["bounds"][3]
        for tile in catalog_tiles
    )
    passed = bool(
        phase == "dashboard"
        and len(tiles) == 2
        and repaired.get("action") == "click"
        and repaired.get("target_coords")
        and repaired.get("kb_key") is None
        and recovered_phase == "dashboard"
        and recovered_decision.get("action") == "click"
        and str(recovered_decision.get("target_text") or "").startswith("Featured Survey")
        and stale_overlay_phase == "survey_question"
        and catalog_phase == "dashboard"
        and len(catalog_tiles) == 2
        and catalog_decision.get("action") == "click"
        and catalog_tap_inside_card
    )
    if passed:
        logger.info("[SELF-CHECK] Dashboard routing regression checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Dashboard routing failed: phase=%s tiles=%s decision=%s "
            "recovered_phase=%s recovered_decision=%s stale_overlay_phase=%s "
            "catalog_phase=%s catalog_tiles=%s catalog_decision=%s tap_inside=%s",
            phase, tiles, repaired, recovered_phase, recovered_decision, stale_overlay_phase,
            catalog_phase, catalog_tiles, catalog_decision, catalog_tap_inside_card,
        )
    return passed


def start_gate_regression_self_check() -> bool:
    ocr = (
        "We have some exciting survey opportunities available.\n"
        "Your Survey Details Average length: 10 minutes\n"
        "Simply click on 'start' for a chance to share your opinions.\n"
        "Start!\nTerms & Conditions Privacy Policy\nAbout Cookies On This Site"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="start-gate",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    phase = classify_screen_phase(ocr, [])
    first = navigation_cta_decision(obs)
    replay = inspect_decision(obs, {
        "action": "click", "target_text": "Continue »",
        "target_coords": [500, 780], "coordinate_authoritative": True,
        "confidence_score": 0.9, "postcondition": "screen changed",
    })
    coords = (first or {}).get("target_coords") or []
    passed = bool(
        start_gate_visible(ocr)
        and phase == "survey_landing"
        and first and first.get("action") == "click"
        and "start" in str(first.get("target_text") or "").lower()
        and isinstance(coords, list) and 380 <= int(coords[1]) <= 450
        and replay and "start" in str(replay.get("target_text") or "").lower()
    )
    if passed:
        logger.info("[SELF-CHECK] Start! gate taps Start, not Continue.")
    else:
        logger.error("[SELF-CHECK] Start! gate failed phase=%s first=%s replay=%s", phase, first, replay)
    return passed


def i_agree_consent_regression_self_check() -> bool:
    _I_AGREE_SESSION["tapped"] = False
    ocr = (
        "See choreograph.com privacy policy\n"
        "Continue"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="agree",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    first = i_agree_consent_decision(obs)
    vetoed = prefer_progression_over_repeat(
        {"action": "click", "target_coords": [420, 776], "coordinate_authoritative": True,
         "confidence_score": 0.9, "postcondition": "I Agree selected"},
        obs, 2,
    )
    repaired = i_agree_consent_decision(obs, vetoed)
    _I_AGREE_SESSION["tapped"] = True
    nxt = i_agree_consent_decision(obs)
    _I_AGREE_SESSION["tapped"] = False
    passed = bool(
        i_agree_consent_visible(ocr)
        and first and "agree" in str(first.get("target_text") or "").lower()
        and 680 <= int((first.get("target_coords") or [0, 0])[-1]) <= 840
        and repaired and "agree" in str(repaired.get("target_text") or "").lower()
        and nxt and "continue" in str(nxt.get("target_text") or "").lower()
        and int((nxt.get("target_coords") or [0, 999])[-1]) <= 905
    )
    if passed:
        logger.info("[SELF-CHECK] I Agree then Continue (not nav-bar) checks passed.")
    else:
        logger.error("[SELF-CHECK] I Agree failed first=%s repaired=%s next=%s", first, repaired, nxt)
    return passed


def consent_and_embedded_cta_regression_self_check() -> bool:
    """Guard cookie overlays and question prose containing navigation words."""
    cookie_ocr = """Your Cookie Choices
We and our partners use cookies and similar technologies.
More Options
Accept
Reject
Powered by Transcend."""
    cookie_observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="cookie-overlay",
        ocr_text=cookie_ocr, ui_nodes=[], kb={}, persona={},
        screen_phase=classify_screen_phase(cookie_ocr, []), survey_tiles=[],
    )
    consent = consent_overlay_decision(cookie_observation)

    question_ocr = """Questions 2/1
In addition to regular surveys, would you be willing to participate in Webcam Interviews?
If your schedule allowed, would you be willing to participate?
Yes, I would be willing
No, I would not be willing to participate
Continue"""
    option_nodes = [
        {
            "id": 31, "text": "Yes, I would be willing", "content_desc": "",
            "resource_id": "", "class": "android.widget.RadioButton",
            "bounds": [170, 1650, 1260, 1850], "clickable": True,
            "checkable": True, "checked": False, "editable": False,
            "enabled": True, "focusable": True, "selected": False,
        },
        {
            "id": 33, "text": "No, I would not be willing to participate", "content_desc": "",
            "resource_id": "", "class": "android.widget.RadioButton",
            "bounds": [170, 1880, 1260, 2080], "clickable": True,
            "checkable": True, "checked": False, "editable": False,
            "enabled": True, "focusable": True, "selected": False,
        },
        {
            "id": 32, "text": "Continue", "content_desc": "",
            "resource_id": "", "class": "android.widget.Button",
            "bounds": [180, 2240, 1260, 2410], "clickable": True,
            "checkable": False, "checked": False, "editable": False,
            "enabled": True, "focusable": True, "selected": False,
        },
    ]
    question_phase = classify_screen_phase(question_ocr, option_nodes)
    question_observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="webcam-question",
        ocr_text=question_ocr, ui_nodes=option_nodes, kb={}, persona={},
        screen_phase=question_phase, survey_tiles=[],
    )
    preference = configured_personal_answer_decision(question_observation)
    landing_ocr = """You've qualified for this survey!
Click below to get started and earn your rewards.
Survey will take around 21 minutes
Survey Success Tip
Participate"""
    stale_catalog_nodes = [{
        "id": 80,
        "text": (
            "Earn Surveys Games Account 21 min €0.69 10 min €0.39 "
            "17 min €0.49 19 min €0.46"
        ),
        "content_desc": "", "resource_id": "", "class": "android.view.View",
        "bounds": [0, 0, 1440, 3088], "clickable": False,
        "checkable": False, "checked": False, "editable": False,
        "enabled": True, "focusable": False, "selected": False,
    }]
    landing_phase = classify_screen_phase(landing_ocr, stale_catalog_nodes)
    landing_observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="qualified-landing",
        ocr_text=landing_ocr, ui_nodes=stale_catalog_nodes, kb={}, persona={},
        screen_phase=landing_phase, survey_tiles=[],
    )
    landing_decision = navigation_cta_decision(landing_observation)
    canvas_landing_ocr = landing_ocr.replace("\nParticipate", "")
    canvas_observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="canvas-landing",
        ocr_text=canvas_landing_ocr, ui_nodes=stale_catalog_nodes, kb={}, persona={},
        screen_phase=classify_screen_phase(canvas_landing_ocr, stale_catalog_nodes),
        survey_tiles=[],
    )
    canvas_decision = navigation_cta_decision(canvas_observation)
    passed = bool(
        cookie_observation.screen_phase == "consent_overlay"
        and consent
        and consent.get("action") == "click"
        and str(consent.get("target_text") or "").lower().startswith(COOKIE_CONSENT_ACTION)
        and question_phase == "survey_question"
        and preference
        and preference.get("target_text") == (
            "Yes, I would be willing"
            if WEBCAM_INTERVIEW_WILLING
            else "No, I would not be willing to participate"
        )
        and preference.get("target_element_id") == (31 if WEBCAM_INTERVIEW_WILLING else 33)
        and landing_phase == "survey_landing"
        and landing_decision
        and landing_decision.get("action") == "click"
        and landing_decision.get("target_text") == "Participate"
        and landing_decision.get("coordinate_authoritative") is True
        and isinstance(landing_decision.get("target_coords"), list)
        and int(landing_decision["target_coords"][1]) >= 850
        and canvas_observation.screen_phase == "survey_landing"
        and canvas_decision
        and canvas_decision.get("target_text") == "Participate"
        and canvas_decision.get("coordinate_authoritative") is True
        and isinstance(canvas_decision.get("target_coords"), list)
        and int(canvas_decision["target_coords"][1]) >= 850
    )
    if passed:
        logger.info(
            "[SELF-CHECK] Cookie overlay, qualified landing and embedded-CTA "
            "question routing checks passed."
        )
    else:
        logger.error(
            "[SELF-CHECK] Cookie/question routing failed: cookie_phase=%s consent=%s "
            "question_phase=%s preference=%s landing_phase=%s landing_decision=%s "
            "canvas_phase=%s canvas_decision=%s",
            cookie_observation.screen_phase, consent, question_phase, preference,
            landing_phase, landing_decision, canvas_observation.screen_phase, canvas_decision,
        )
    return passed


def postcode_and_learning_regression_self_check() -> bool:
    """Guard KB text entry and confidence-gated semantic-screen reuse."""
    ocr_text = "Postcodes: E.g., A96 for IE Next Privacy Policy"
    phase = classify_screen_phase(ocr_text, [])
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="postcode-form",
        ocr_text=ocr_text, ui_nodes=[],
        kb={"area_code": "D22", "postal_code": "D22V048"}, persona={},
        screen_phase=phase, survey_tiles=[],
    )
    text_decision = configured_text_answer_decision(observation)
    signature = semantic_screen_signature(observation)
    learned_observation = Observation(
        step=observation.step, screenshot=None,
        image_width=observation.image_width, image_height=observation.image_height,
        device_width=observation.device_width, device_height=observation.device_height,
        screen_hash=observation.screen_hash, ocr_text=observation.ocr_text,
        ui_nodes=observation.ui_nodes,
        kb={
            **observation.kb,
            "learned_screen_actions": {
                signature: {
                    "successes": 100, "failures": 0,
                    "decision": {
                        "action": "type_text", "target_text": "Postcode input field",
                        "target_coords": [500, 750], "input_payload": "stale",
                        "kb_key": "area_code", "kb_write": False,
                        "postcondition": "field contains D22",
                    },
                }
            },
        },
        persona={}, screen_phase=phase, survey_tiles=[],
    )
    learned = learned_action_decision(learned_observation)
    passed = bool(
        phase == "survey_question"
        and text_decision
        and text_decision.get("action") == "type_text"
        and text_decision.get("input_payload") == "D22"
        and text_decision.get("kb_key") == "area_code"
        and text_decision.get("target_coords") == [500, 750]
        and learned
        and learned.get("input_payload") == "D22"
        and float(learned.get("learned_action_confidence") or 0) >= LEARNED_ACTION_MIN_CONFIDENCE
        and learned_confidence(1, 1) < learned_confidence(1, 0)
    )
    if passed:
        logger.info("[SELF-CHECK] Postcode KB routing and learned-screen confidence checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Postcode/learning routing failed: phase=%s text=%s learned=%s",
            phase, text_decision, learned,
        )
    return passed


def advanced_controls_regression_self_check() -> bool:
    """Guard complex-control detection, completion rules and permission safety."""
    checkbox_nodes = [
        {
            "id": 1, "text": "Option A", "content_desc": "", "class": "CheckBox",
            "bounds": [100, 700, 600, 820], "clickable": True, "checkable": True,
            "checked": True, "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 2, "text": "Option B", "content_desc": "", "class": "CheckBox",
            "bounds": [100, 850, 600, 970], "clickable": True, "checkable": True,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
    ]
    multi = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="multi",
        ocr_text="Select all that apply: Option A Option B", ui_nodes=checkbox_nodes,
        kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )

    matrix_nodes: list[dict[str, Any]] = []
    node_id = 10
    for y, checked_column in ((900, 0), (1200, 1)):
        for column, x in enumerate((500, 850)):
            matrix_nodes.append({
                "id": node_id, "text": "", "content_desc": "", "class": "RadioButton",
                "bounds": [x, y, x + 80, y + 80], "clickable": True, "checkable": True,
                "checked": column == checked_column, "editable": False,
                "enabled": True, "selected": False,
            })
            node_id += 1
    matrix = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="matrix",
        ocr_text="For each row choose Strongly disagree or Strongly agree",
        ui_nodes=matrix_nodes, kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )

    permission_nodes = [
        {
            "id": 30, "text": "While using the app", "content_desc": "", "class": "Button",
            "bounds": [200, 1900, 1240, 2050], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 31, "text": "Don't allow", "content_desc": "", "class": "Button",
            "bounds": [200, 2100, 1240, 2250], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
    ]
    permission_text = "Allow this app to access your camera? While using the app Don't allow"
    permission_phase = classify_screen_phase(permission_text, permission_nodes)
    permission = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="permission",
        ocr_text=permission_text, ui_nodes=permission_nodes, kb={}, persona={},
        screen_phase=permission_phase, survey_tiles=[],
    )
    permission_action = permission_dialog_decision(permission)
    expected_permission = (
        "While using the app"
        if PERMISSION_POLICY == "allow_all" or (
            PERMISSION_POLICY != "deny_all" and ALLOW_CAMERA_PERMISSION
        )
        else "Don't allow"
    )
    required_actions = (
        "scroll_left", "scroll_right", "swipe", "drag", "set_slider",
        "select_matrix_cell", "type_comment", "open_date_picker",
        "open_time_picker", "pick_file", "handle_permission",
    )
    passed = bool(
        multi_select_question(multi)
        and not answer_already_selected(multi)
        and matrix_question(matrix)
        and matrix_question_complete(matrix)
        and permission_phase == "permission_dialog"
        and permission_action
        and permission_action.get("target_text") == expected_permission
        and all(action in SYSTEM_PROMPT for action in required_actions)
    )
    if passed:
        logger.info("[SELF-CHECK] Advanced-control and permission-policy checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Advanced-control checks failed: multi=%s matrix=%s/%s "
            "permission=%s action=%s",
            multi_select_question(multi), matrix_question(matrix), matrix_question_complete(matrix),
            permission_phase, permission_action,
        )
    return passed


def question_progression_regression_self_check() -> bool:
    """Guard answer-selected -> bottom-forward routing without fixed pixels."""
    nodes = [
        {
            "id": 10, "text": "Both domestic and international", "content_desc": "",
            "bounds": [80, 1220, 1360, 1390], "clickable": True,
            "checkable": True, "checked": True, "editable": False,
            "enabled": True, "focusable": True, "selected": False,
        },
        {
            "id": 11, "text": "", "content_desc": "", "bounds": [625, 2690, 815, 2880],
            "clickable": True, "checkable": False, "checked": False,
            "editable": False, "enabled": True, "focusable": True, "selected": False,
        },
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="selected-question",
        ocr_text="When you fly? Both domestic and international", ui_nodes=nodes,
        kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    decision = survey_next_decision(observation) if answer_already_selected(observation) else None
    passed = bool(
        decision
        and decision.get("action") == "click"
        and (
            decision.get("target_element_id") == 11
            or (
                is_progression_cta(str(decision.get("target_text") or ""))
                and isinstance(decision.get("target_coords"), list)
            )
        )
        and decision.get("postcondition") == "screen changed"
    )
    if passed:
        logger.info("[SELF-CHECK] Selected-answer progression checks passed.")
    else:
        logger.error("[SELF-CHECK] Selected-answer progression failed: %s", decision)
    return passed


def answer_grounding_regression_self_check() -> bool:
    """Guard exact KB answers from being executed through a blank wrong-row node."""
    nodes = [
        {
            "id": 144, "text": "", "content_desc": "", "bounds": [70, 740, 1370, 900],
            "clickable": True, "checkable": True, "checked": False,
            "editable": False, "enabled": True, "focusable": True, "selected": False,
        },
        {
            "id": 145, "text": "Yes, I smoke", "content_desc": "", "bounds": [240, 760, 700, 850],
            "clickable": False, "checkable": False, "checked": False,
            "editable": False, "enabled": True, "focusable": False, "selected": False,
        },
        {
            "id": 150, "text": "No, I don't smoke", "content_desc": "", "bounds": [240, 1320, 740, 1410],
            "clickable": False, "checkable": False, "checked": False,
            "editable": False, "enabled": True, "focusable": False, "selected": False,
        },
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="smoking-question",
        ocr_text="Do you smoke? Yes, I smoke. No, I don't smoke.", ui_nodes=nodes,
        kb={"smoking_status": "No, I don't smoke"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    exact = exact_kb_option_decision(observation)
    llm = {
        "screen_state": "survey_question", "action": "click",
        "target_element_id": 144, "target_text": "No, I don't smoke",
        "target_coords": [144, 626], "confidence_score": 0.95,
    }
    repaired = repair_decision_for_screen(llm, observation, quiet=True)
    passed = bool(
        exact
        and exact.get("target_element_id") == 150
        and exact.get("target_text") == "No, I don't smoke"
        and repaired.get("target_element_id") == 150
    )
    if passed:
        logger.info("[SELF-CHECK] Exact-KB answer grounding checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Exact-KB answer grounding failed: exact=%s repaired=%s",
            exact, repaired,
        )
    return passed


def world_change_open_text_regression_self_check() -> bool:
    """Empty 'Type your answer here' must type a 5+ word sentence, never Submit."""
    ocr = (
        "Please answer the following question to proceed\n"
        "Imagine you have the power to change one thing about the world. "
        "What issue would you address, and what steps would you take?\n"
        "Type your answer here\nPlease fill in this field.\nSubmit\nEnglish (US)"
    )
    empty = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="world-empty",
        ocr_text=ocr, ui_nodes=[
            {"id": 18, "text": "Submit", "content_desc": "", "class": "Button",
             "bounds": [455, 1656, 984, 1762], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ], kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    _OPEN_TEXT_TYPED.clear()
    _OPEN_TEXT_DONE.clear()
    first = open_text_answer_decision(empty)
    nxt = survey_next_decision(empty)
    repaired = prefer_progression_over_repeat(
        {"action": "type_text", "input_payload": "Climate Change",
         "target_coords": [266, 500], "confidence_score": 0.9},
        empty, 3,
    )
    payload = str((first or {}).get("input_payload") or "")
    filled = Observation(
        step=1, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="world-filled",
        ocr_text=(
            "Imagine you have the power to change one thing about the world.\n"
            "I would address climate change by using public transport, "
            "cutting household waste, and backing cleaner energy locally.\n"
            "Submit"
        ),
        ui_nodes=empty.ui_nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _OPEN_TEXT_TYPED[open_text_screen_key(filled)] = payload
    second = open_text_answer_decision(filled)
    passed = bool(
        open_text_question_visible(ocr)
        and open_text_field_empty(empty)
        and first and first.get("action") == "type_text"
        and open_text_word_count(payload) >= 5
        and "type your answer" not in payload.lower()
        and nxt and nxt.get("action") == "type_text"
        and repaired and repaired.get("action") == "type_text"
        and second and second.get("action") in {"click", "back"}
        and second.get("action") != "type_text"
        and (
            second.get("action") == "back"
            or "submit" in str(second.get("target_text") or "").lower()
        )
    )
    if passed:
        logger.info("[SELF-CHECK] World-change empty box types a sentence, then Submit.")
    else:
        logger.error(
            "[SELF-CHECK] World-change failed first=%s next=%s repaired=%s second=%s payload=%r",
            first, nxt, repaired, second, payload,
        )
    return passed


def quoted_select_instruction_regression_self_check() -> bool:
    """'Please select the X option' must tap X then Continue, not loop on X."""
    messy = (
        "Please select the ‘Somewhat , disagree’ option from the below: "
        "O Neither agree nor di Continue"
    )
    clean = (
        "Please select the 'Somewhat disagree' option from the below:\n"
        "Strongly agree\nSomewhat agree\nNeither agree nor disagree\n"
        "Somewhat disagree\nStrongly disagree\n« Back\nContinue »"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="quoted-select",
        ocr_text=clean, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    _SELECT_ONE_SESSION.update({"key": "", "taps": 0, "misses": 0, "verified": False})
    first = quoted_instruction_decision(obs)
    second = quoted_instruction_decision(obs)
    _SELECT_ONE_SESSION.update({"key": "", "taps": 0, "misses": 0, "verified": False})
    inspected = critique_decision(obs, {
        "action": "click", "target_text": "Somewhat disagree",
        "target_coords": [499, 570], "confidence_score": 0.9,
        "postcondition": "screen changed",
    })
    passed = bool(
        quoted_select_pick(messy) == "Somewhat disagree"
        and quoted_select_instruction_visible(messy)
        and looks_like_single_choice(clean)
        and classify_screen_phase(clean, []) == "survey_question"
        and first and first.get("action") == "select_then_continue"
        and first.get("target_text") == "Somewhat disagree"
        and int((first.get("target_coords") or [500, 0])[0]) <= 280
        and first.get("continue_coords")
        and int((first.get("continue_coords") or [0, 0])[1]) < 900
        and second and second.get("action") == "click"
        and "continue" in str(second.get("target_text") or "").lower()
        and inspected and inspected.get("action") == "select_then_continue"
    )
    if passed:
        logger.info("[SELF-CHECK] Quoted-select taps Somewhat disagree then Continue.")
    else:
        logger.error(
            "[SELF-CHECK] Quoted-select failed pick=%r first=%s second=%s inspected=%s",
            quoted_select_pick(messy), first, second, inspected,
        )
    return passed


def smartphone_brand_regression_self_check() -> bool:
    """ADB/KB brand must tap the matching card then the purple arrow, never Continue first."""
    ocr = (
        "This question is required\n"
        "Which brand of smartphone do you currently use?\n"
        "Samsung\nApple iPhone\nGoogle Pixel\nXiaomi / Redmi\n"
        "Oppo / OnePlus\nOther Android phone\nOther"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="phone-brand",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _DEVICE_BRAND_CACHE["raw"] = "samsung SM-A"
    _SELECT_ONE_SESSION.update({"key": "", "taps": 0, "misses": 0, "verified": False})
    first = smartphone_brand_decision(obs)
    second = smartphone_brand_decision(obs)
    obs.kb = {"smartphone_brand": "Samsung"}
    _SELECT_ONE_SESSION.update({"key": "", "taps": 0})
    reused = smartphone_brand_decision(obs)
    repaired = prefer_progression_over_repeat(
        {"action": "click", "target_text": "Samsung", "target_coords": [499, 400],
         "confidence_score": 0.9, "postcondition": "screen changed"},
        obs, stagnation_count=3,
    )
    _DEVICE_BRAND_CACHE["raw"] = None
    _SELECT_ONE_SESSION.update({"key": "", "taps": 0, "misses": 0, "verified": False})
    passed = bool(
        smartphone_brand_question_visible(ocr)
        and survey_validation_error(obs)
        and first and first.get("action") == "select_then_continue"
        and first.get("target_text") == "Samsung"
        and first.get("kb_key") == "smartphone_brand"
        and first.get("kb_write") is True
        and first.get("continue_coords")
        and second and str(second.get("target_text") or "") in {"Samsung", "arrow", "Continue"}
        and reused and reused.get("target_text") == "Samsung"
        and repaired and str(repaired.get("action")) in {"select_then_continue", "click"}
        and "continue" not in str(repaired.get("target_text") or "").lower()
    )
    if passed:
        logger.info("[SELF-CHECK] Smartphone brand taps Samsung then purple arrow; KB reuse works.")
    else:
        logger.error("[SELF-CHECK] Phone brand failed first=%s second=%s reused=%s repaired=%s",
                     first, second, reused, repaired)
    return passed
