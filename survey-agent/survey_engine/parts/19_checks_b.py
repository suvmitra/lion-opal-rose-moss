# 19_checks_b.py — shared engine namespace (do not import directly)




def select_all_apply_regression_self_check() -> bool:
    ocr = (
        "Which of the following claims would be important to you when choosing a bread to buy?\n"
        "Select all that apply\nCholesterol lowering\nLow in fat\nHigh in fibre\n"
        "No preservatives\nNo added sugar\nHigh in protein"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="claims",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _SELECT_ALL_SESSION.update({"key": "", "done": [], "planned": [], "scrolls": 0})
    first = select_all_apply_decision(obs)
    _SELECT_ALL_SESSION["done"] = [str(first.get("select_all_pick") or "No preservatives")]
    second = select_all_apply_decision(obs)
    _SELECT_ALL_SESSION["done"] = list(dict.fromkeys(
        list(_SELECT_ALL_SESSION.get("done") or []) + [str(second.get("select_all_pick") or "High in fibre")]
    ))
    third = select_all_apply_decision(obs)
    human = capture_human_answer_decision(obs, "Confidence 0.00 is below safety threshold.")
    passed = bool(
        select_all_apply_visible(ocr)
        and first and first.get("action") == "select_option"
        and first.get("select_all_pick")
        and second and second.get("action") == "select_option"
        and str(second.get("select_all_pick") or "") != str(first.get("select_all_pick") or "")
        and third and third.get("action") in {"click", "scroll_down"}
        and human and str(human.get("action") or "") in {"click", "scroll_down", "select_option"}
    )
    if passed:
        logger.info("[SELF-CHECK] Select-all two ticks then Continue/scroll checks passed.")
    else:
        logger.error("[SELF-CHECK] Select-all failed first=%s second=%s third=%s human=%s",
                     first, second, third, human)
    return passed


def brand_bought_select_all_regression_self_check() -> bool:
    ocr = (
        "Which of the following brands of bread have you ever bought?\n"
        "Please select at least 1 answer (you selected 0).\n"
        "Select all that apply\nHovis\nJohnson, Mooney and O'Brien\nBrennans\n"
        "Others please specify\nNone of these\nContinue »"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="brands-bought",
        ocr_text=ocr, ui_nodes=[],
        kb={"bread_brands_aware": "Brennans, Johnston Mooney and OBrien"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    _SELECT_ALL_SESSION.update({
        "key": "select-all-claims",
        "done": ["No preservatives", "High in fibre"],
        "planned": ["No preservatives", "High in fibre", "Low in fat"],
        "scrolls": 4,
    })
    first = select_all_apply_decision(obs)
    target = str((first or {}).get("target_text") or "")
    coords = first.get("target_coords") if first else None
    planned = first.get("intended_options") if first else []
    passed = bool(
        select_all_apply_visible(ocr)
        and not open_text_question_visible(ocr)
        and first and first.get("action") == "select_option"
        and re.search(r"(?i)brennan|johnson|johnston|hovis", target)
        and "preservative" not in target.lower()
        and "fibre" not in target.lower()
        and isinstance(coords, list) and int(coords[1]) >= 450
        and str(planned).lower().count("johnson") <= 1
    )
    if passed:
        logger.info("[SELF-CHECK] Brand-bought select-all ticks a bread brand, not Continue.")
    else:
        logger.error("[SELF-CHECK] Brand-bought select-all failed first=%s", first)
    return passed


def hovis_unavailable_select_one_regression_self_check() -> bool:
    ocr = (
        "If Hovis was not available in a store when you were shopping would you...\n"
        "Please select an answer.\nSelect one\n"
        "Buy another brand of bread\n"
        "Wait and go to another store to buy Hovis\n"
        "Don't buy any bread\nContinue »"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="hovis-out",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    phase = classify_screen_phase(ocr, [])
    _SELECT_ONE_SESSION.update({"key": "", "taps": 0, "misses": 0, "verified": False})
    first = single_choice_radio_decision(obs)
    nav = navigation_cta_decision(obs)
    inspected = inspect_decision(obs, {
        "action": "click",
        "target_text": "Continue »",
        "target_coords": [500, 855],
        "coordinate_authoritative": True,
        "input_payload": None,
        "confidence_score": 0.9,
        "postcondition": "screen changed",
    })
    coords = (first or {}).get("target_coords")
    cont = (first or {}).get("continue_coords") or []
    passed = bool(
        phase == "survey_question"
        and looks_like_single_choice(ocr)
        and first and first.get("action") == "select_then_continue"
        and first.get("input_payload")
        and "buy another" in str(first.get("input_payload")).lower()
        and isinstance(coords, list) and 400 <= int(coords[1]) <= 650
        and isinstance(cont, list) and int(cont[1]) < 900
        and nav and nav.get("action") == "select_then_continue"
        and inspected and inspected.get("action") == "select_then_continue"
    )
    if passed:
        logger.info("[SELF-CHECK] Hovis-unavailable Select-one taps a radio with payload, not Continue.")
    else:
        logger.error("[SELF-CHECK] Hovis-unavailable failed phase=%s first=%s nav=%s", phase, first, nav)
    return passed


def rl_generalization_regression_self_check() -> bool:
    ocr = (
        "If Brennans was not available in a store when you were shopping would you...\n"
        "Please select an answer.\nSelect one\n"
        "Buy another brand of bread\n"
        "Wait and go to another store to buy Brennans\n"
        "Don't buy any bread\nContinue »"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="unseen-select",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    klass = generalized_widget_class(obs)
    gen = generalized_unseen_router(obs)
    update_rl_policy(obs, gen or {}, True, after=obs)
    replay = rl_policy_decision(obs)
    payload = str((gen or {}).get("input_payload") or "")
    passed = bool(
        klass == "select_one"
        and gen and gen.get("action") in {"select_option", "select_then_continue"}
        and payload
        and "buy another" in payload.lower()
        and replay and replay.get("action") in {"select_option", "click", "select_then_continue"}
        and replay.get("input_payload")
    )
    if passed:
        logger.info("[SELF-CHECK] Unseen Select-one generalizes and RL replays a payload.")
    else:
        logger.error("[SELF-CHECK] RL/generalize failed class=%s gen=%s replay=%s", klass, gen, replay)
    return passed


def screen_ask_brief(obs: Observation) -> str:
    """Compact instruction the VLM cannot miss: what this screen actually asks."""
    q = current_question_text(obs)
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    bits = [mindset_prompt(), f"VISIBLE QUESTION: {q[:220]}"]
    if "please provide an answer" in blob or survey_validation_error(obs):
        bits.append("VALIDATION: empty required box. TYPE an answer. Do not Continue yet.")
    if "select one" in blob or "please select an answer" in blob:
        bits.append("SELECT ONE radio is empty. payload MUST be an option such as Buy another brand of bread. Never Continue with payload=None.")
    if "any other" in blob:
        bits.append("FOLLOW-UP: heading is the previous answer. Type OTHER brands into the empty box.")
    bits.append("Then tap the green Continue pill using target_coords from the screenshot.")
    return "ASK=" + " | ".join(bits)


def other_brand_followup_regression_self_check() -> bool:
    ocr = (
        "There were problems with some of the data you entered in the survey.\n"
        "Brennans, Johnston Mooney and OBrien\n"
        "...any other brand of bread you can think of?\n"
        "Please provide an answer\nPlease be as specific as possible\nContinue »"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="other",
        ocr_text=ocr, ui_nodes=[],
        kb={"bread_brands_aware": "Brennans, Johnston Mooney and OBrien"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    _OPEN_TEXT_TYPED.clear()
    _OPEN_TEXT_DONE.clear()
    first = open_text_answer_decision(obs)
    payload = str((first or {}).get("input_payload") or "")
    _OPEN_TEXT_TYPED[open_text_screen_key(obs)] = payload
    filled = Observation(
        step=1, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="other-filled",
        ocr_text=ocr + "\nBatch, Pat the Baker, SuperValu",
        ui_nodes=[], kb=obs.kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    second = open_text_answer_decision(filled)
    passed = bool(
        first and first.get("action") == "type_text"
        and "brennans" not in payload.lower()
        and "clear and useful" not in payload.lower()
        and ("batch" in payload.lower() or "pat" in payload.lower())
        and second
        and second.get("action") == "click"
    )
    if passed:
        logger.info("[SELF-CHECK] Other-brand follow-up types extra brands, not Continue.")
    else:
        logger.error("[SELF-CHECK] Other-brand follow-up failed first=%s", first)
    return passed


def bread_brands_text_regression_self_check() -> bool:
    ocr = (
        "Please state what brands of breads you are aware of?\n"
        "Please be as specific as possible\nContinue »\nEnglish (US)"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="brands",
        ocr_text=ocr, ui_nodes=[],
        kb={"bread_brands_aware": "Brennans, Johnston Mooney and OBrien"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    _OPEN_TEXT_TYPED.clear()
    first = open_text_answer_decision(obs)
    _OPEN_TEXT_TYPED[question_fingerprint(obs)] = "Brennans, Johnston Mooney and OBrien"
    second = prefer_progression_over_repeat(
        {"action": "type_text", "input_payload": "Brennans, Johnston Mooney and OBrien",
         "confidence_score": 1.0, "target_text": ""},
        obs, 0,
    )
    passed = bool(
        open_text_question_visible(ocr)
        and resolve_text_kb_key(ocr) == "bread_brands_aware"
        and first and first.get("action") == "type_text"
        and "'" not in str(first.get("input_payload") or "")
        and second and second.get("action") in {"click", "scroll_down", "back"}
        and second.get("action") != "type_text"
    )
    if passed:
        logger.info("[SELF-CHECK] Bread-brand type-then-Continue checks passed.")
    else:
        logger.error("[SELF-CHECK] Bread-brand failed first=%s second=%s", first, second)
    return passed


def maxdiff_regression_self_check() -> bool:
    ocr = (
        "What factors were MOST IMPORTANT, and which were the LEAST IMPORTANT "
        "to you on deciding what Bread to buy?\nScreen 1 of 20\n"
        "Most Important\nREPLACE with relevant text\nLeast Important\n"
        "Price\nBrand\nAvailability where I shop\nSoftness of the bread\n"
        "Calorie content\nOccasions it will be used\nContinue »"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="maxdiff",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    _MAXDIFF_SESSION.update({"key": "", "most": "", "least": "", "scrolls": 0, "force_scroll": False})
    _SELECT_ALL_SESSION.update({"key": "", "done": [], "planned": [], "scrolls": 0})
    first = maxdiff_decision(obs)
    _MAXDIFF_SESSION["most"] = str(first.get("maxdiff_row") or "Brand")
    second = maxdiff_decision(obs)
    _MAXDIFF_SESSION["least"] = str(second.get("maxdiff_row") or "Calorie content")
    third = maxdiff_decision(obs)
    stuck_ocr = (
        "What factors were MOST IMPORTANT, and which were the LEAST IMPORTANT "
        "to you on deciding what Bread to buy?\nScreen 2 of 20\n"
        "Most Important\nLeast Important\nHealthiness\nGrains in the bread\n"
        "Freshness\nAvailability where I shop\nOccasions it will be used"
    )
    stuck = Observation(
        step=0, screenshot="/tmp/missing_maxdiff.png", image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="stuck",
        ocr_text=stuck_ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _MAXDIFF_SESSION.update({"key": "", "most": "", "least": "", "scrolls": 0, "force_scroll": False})
    _SELECT_ALL_SESSION.update({"key": "", "done": [], "planned": [], "scrolls": 0})
    maxdiff_decision(stuck)  # establish page key
    _MAXDIFF_SESSION["most"] = "Freshness"
    _MAXDIFF_SESSION["least"] = "Availability"
    stuck_dec = maxdiff_decision(stuck)
    _MAXDIFF_SESSION.update({"key": "maxdiff-page-1", "most": "Brand", "least": "Calorie content", "scrolls": 0, "force_scroll": False})
    no_retap = maxdiff_decision(obs)
    passed = bool(
        maxdiff_question_visible(ocr)
        and not looks_like_single_choice(ocr)
        and not matrix_grid_visible(obs)
        and first and first.get("action") == "select_matrix_cell"
        and first.get("column_text") == "Most Important"
        and int((first.get("target_coords") or [0, 0])[0]) == 187
        and second and second.get("action") == "select_matrix_cell"
        and second.get("column_text") == "Least Important"
        and int((second.get("target_coords") or [0, 0])[0]) == 870
        and str(second.get("maxdiff_row") or "").lower() != str(first.get("maxdiff_row") or "").lower()
        and third and third.get("action") == "click"
        and "continue" in str(third.get("target_text") or "").lower()
        and stuck_dec and stuck_dec.get("action") == "scroll_down"
        and no_retap and no_retap.get("action") == "click"
        and "continue" in str(no_retap.get("target_text") or "").lower()
    )
    if passed:
        logger.info("[SELF-CHECK] MaxDiff Most then Least then Continue checks passed.")
    else:
        logger.error("[SELF-CHECK] MaxDiff failed first=%s second=%s third=%s", first, second, third)
    return passed


def carousel_row_regression_self_check() -> bool:
    ocr = (
        "Change in the types of bread bought\nSelect one in each row\n"
        "Bagels\nMore often\nAbout the same\nLess often\n"
        "I don't buy this type of bread\nDon't know / can't remember\nContinue »"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="bagel",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    _CAROUSEL_SESSION.update({"item": "", "answered": False, "done": [], "right_stagnant": 0, "tap_try": 0, "left_reviews": 0, "review_done": False})
    _MAXDIFF_SESSION.update({"key": "", "most": "", "least": "", "scrolls": 0, "force_scroll": False})
    _SELECT_ALL_SESSION.update({"key": "", "done": [], "planned": [], "scrolls": 0})
    first = carousel_row_decision(obs)
    _CAROUSEL_SESSION.update({"item": "Bagels", "answered": True, "done": [], "right_stagnant": 0})
    second = carousel_row_decision(obs)
    _CAROUSEL_SESSION.update({"item": "Bagels", "answered": True, "done": ["bagels"], "right_stagnant": 2})
    last = carousel_row_decision(obs)
    banner_ocr = (
        "There were problems with some of the data you entered in the survey. "
        "You will find the questions with errors below; please follow the "
        "instructions attached to each question.\n"
        "Change in the types of bread bought\nPlease select an answer.\n"
        "Select one in each row\nBaps\nMore often\nAbout the same\nLess often"
    )
    banner_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="baps-banner",
        ocr_text=banner_ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    _CAROUSEL_SESSION.update({"item": "", "answered": False, "done": [], "right_stagnant": 0, "tap_try": 0, "left_reviews": 0, "review_done": False})
    _MAXDIFF_SESSION.update({"key": "", "most": "", "least": "", "scrolls": 0, "force_scroll": False})
    _SELECT_ALL_SESSION.update({"key": "", "done": [], "planned": [], "scrolls": 0})
    banner_item = carousel_current_item(banner_obs)
    banner_dec = carousel_row_decision(banner_obs)
    thanks_ocr = (
        "There were problems with some of the data you entered in the survey.\n"
        "Change in the types of bread bought\nPlease select an answer.\n"
        "Select one in each row\n"
        "Thanks for those answers, please click continue to move to the next question\n"
        "Continue »\nAccessibility Statement - Help"
    )
    thanks_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="thanks",
        ocr_text=thanks_ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    _CAROUSEL_SESSION.update({"item": "", "answered": False, "done": [], "right_stagnant": 0, "tap_try": 0, "left_reviews": 0})
    thanks_dec = carousel_row_decision(thanks_obs)
    passed = bool(
        carousel_row_question_visible(ocr)
        and classify_screen_phase(ocr, []) == "survey_question"
        and not looks_like_single_choice(ocr)
        and carousel_current_item(obs) == "Bagels"
        and banner_item == "Baps"
        and banner_dec and banner_dec.get("action") == "select_option"
        and first and first.get("action") == "select_option"
        and "about the same" in str(first.get("target_text") or "").lower()
        and int((first.get("target_coords") or [0, 0])[0]) == 500
        and int((banner_dec.get("target_coords") or [0, 0])[1]) >= 650
        and second and second.get("action") == "click"
        and second.get("carousel_advance")
        and "continue" not in str(second.get("target_text") or "").lower()
        and last and last.get("action") == "click"
        and "continue" in str(last.get("target_text") or "").lower()
        and carousel_thanks_visible(thanks_ocr)
        and thanks_dec and thanks_dec.get("action") == "click"
        and "continue" in str(thanks_dec.get("target_text") or "").lower()
        and not thanks_dec.get("carousel_advance")
    )
    if passed:
        logger.info("[SELF-CHECK] Carousel answer -> right arrow -> Continue checks passed.")
    else:
        logger.error("[SELF-CHECK] Carousel failed first=%s second=%s last=%s", first, second, last)
    return passed


def occupation_group_regression_self_check() -> bool:
    ocr_text = (
        "To which occupational group does the Chief Income Earner in your household belongs to?\n"
        "The Chief Income Earner is the person in your household with the largest income.\n"
        "Select one\n"
        "Higher managerial/ professional/ administrative (e.g. Doctor, Solicitor, Board Director)\n"
        "Intermediate managerial/ professional/ administrative (e.g. Board director small organisation, middle manager, principle officer in civil service)\n"
        "Supervisory or clerical/ junior managerial/ professional/ administrative (e.g. Office worker, Salesperson)\n"
        "Student\nContinue »"
    )
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="occ",
        ocr_text=ocr_text, ui_nodes=[],
        kb={"current_title": "Lead Data Scientist / Senior Manager", "seniority_level": "Senior Lead / Management",
            "employment_status": "Employed Full-Time", "industry": "Information Technology"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    labels = option_labels_from_observation(observation)
    decision = occupation_group_decision(observation)
    two = parse_human_answer_input("2", labels)
    opt2 = parse_human_answer_input("option 2", labels)
    mm = parse_human_answer_input("middle manager", labels)
    three = parse_human_answer_input("3", labels)
    passed = bool(
        occupation_group_question_visible(ocr_text)
        and not matrix_grid_visible(observation)
        and configured_multi_option_decision(observation) is None
        and all("chief income earner is the person" not in item.lower() for item in labels)
        and any("intermediate" in item.lower() for item in labels)
        and two[0] == "ok" and "intermediate" in two[1][0].lower()
        and opt2[0] == "ok" and "intermediate" in opt2[1][0].lower()
        and mm[0] == "ok" and "middle manager" in mm[1][0].lower()
        and three[0] == "ok" and "supervisory" in three[1][0].lower()
        and decision and decision.get("action") == "select_option"
        and "intermediate" in str(decision.get("target_text") or "").lower()
        and decision.get("kb_key") == "occupation_group"
        and observation_kb_key(observation) == "occupation_group"
    )
    if passed:
        logger.info("[SELF-CHECK] Occupation-group numbering and middle-manager routing checks passed.")
    else:
        logger.error("[SELF-CHECK] Occupation failed labels=%s decision=%s two=%s mm=%s", labels, decision, two, mm)
    return passed


def gender_are_you_inspector_regression_self_check() -> bool:
    ocr_text = (
        "Are you?\nPlease select an answer.\n"
        "Please select one of the below options.\n"
        "Male\nFemale\nNon-Binary\nContinue »\n"
        "There were problems with some of the data you entered in the survey. "
        "You will find the questions with errors below; please follow the instructions attached to each question."
    )
    nodes = [
        {"id": 10, "text": "Male", "content_desc": "", "class": "RadioButton",
         "bounds": [80, 900, 1200, 1100], "clickable": True, "checkable": True,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 11, "text": "Female", "content_desc": "", "class": "RadioButton",
         "bounds": [80, 1120, 1200, 1320], "clickable": True, "checkable": True,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 12, "text": "Non-Binary", "content_desc": "", "class": "RadioButton",
         "bounds": [80, 1340, 1200, 1540], "clickable": True, "checkable": True,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 31, "text": "Continue »", "content_desc": "", "class": "Button",
         "bounds": [480, 1700, 960, 1880], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="areyou",
        ocr_text=ocr_text, ui_nodes=nodes, kb={"gender": "Male"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    labels = option_labels_from_observation(observation)
    exact = exact_kb_option_decision(observation)
    nxt = survey_next_decision(observation)
    bad = {
        "action": "select_option",
        "target_text": "There were problems with some of the data you entered in the survey. You will find the questions with errors below; please follow the instructions attached to each question.",
        "screen_state": "survey_question",
    }
    inspected = inspect_decision(observation, bad)
    cont = inspect_decision(observation, {"action": "click", "target_text": "Continue »", "screen_state": "survey_question"})
    passed = bool(
        gender_choice_screen(observation)
        and survey_validation_error(observation)
        and required_answer_missing(observation)
        and all("problems" not in item.lower() for item in labels)
        and "Male" in labels
        and exact and str(exact.get("target_text")) == "Male"
        and nxt and str(nxt.get("target_text")) == "Male"
        and inspected and str(inspected.get("target_text")) == "Male"
        and cont and str(cont.get("target_text")) == "Male"
        and body_option_coords(observation, "Male")
        and body_option_coords(observation, "Male")[1] >= 400
        and in_header_chrome([343, 30, 431, 79], 3088)
    )
    if passed:
        logger.info("[SELF-CHECK] Are-you gender + inspector banner rejection checks passed.")
    else:
        logger.error("[SELF-CHECK] Are-you inspector failed labels=%s exact=%s nxt=%s inspected=%s cont=%s",
                     labels, exact, nxt, inspected, cont)
    return passed


def residence_and_close_survey_regression_self_check() -> bool:
    ocr_text = (
        "12:02 Survey Where are you living?\n"
        "Select one\nRepublic of Ireland\nNorthern Ireland\nContinue »"
    )
    nodes = [
        {"id": 3, "text": "", "content_desc": "Close Button", "class": "Button",
         "bounds": [40, 80, 140, 180], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 10, "text": "Republic of Ireland", "content_desc": "", "class": "RadioButton",
         "bounds": [80, 700, 1200, 900], "clickable": True, "checkable": True,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 11, "text": "Northern Ireland", "content_desc": "", "class": "RadioButton",
         "bounds": [80, 920, 1200, 1120], "clickable": True, "checkable": True,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 12, "text": "Continue »", "content_desc": "", "class": "Button",
         "bounds": [480, 1300, 960, 1480], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="live",
        ocr_text=ocr_text, ui_nodes=nodes,
        kb={"country": "Ireland", "city": "Dublin", "area_code": "D22"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    labels = option_labels_from_observation(observation)
    exact = exact_kb_option_decision(observation)
    inferred = inferred_preference_decision(observation)
    confirm = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="confirm",
        ocr_text="Close this survey Are you sure? You cannot open it again. GO BACK CLOSE SURVEY",
        ui_nodes=[
            {"id": 1, "text": "GO BACK", "content_desc": "", "class": "Button",
             "bounds": [400, 1500, 700, 1650], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
            {"id": 2, "text": "CLOSE SURVEY", "content_desc": "", "class": "Button",
             "bounds": [740, 1500, 1100, 1650], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ],
        kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    back = close_survey_confirm_decision(confirm)
    passed = bool(
        "close button" not in [item.lower() for item in labels]
        and "continue »" not in [item.lower() for item in labels]
        and observation_kb_key(observation) == "country"
        and exact and "ireland" in str(exact.get("target_text") or "").lower()
        and "close" not in str(exact.get("target_text") or "").lower()
        and inferred and "close" not in str(inferred.get("target_text") or "").lower()
        and close_survey_confirm_visible(confirm)
        and back.get("target_text") == "GO BACK"
        and back.get("terminal_close") is not True
    )
    if passed:
        logger.info("[SELF-CHECK] Residence KB and close-survey GO BACK checks passed.")
    else:
        logger.error("[SELF-CHECK] Residence/close failed labels=%s exact=%s inferred=%s back=%s key=%s",
                     labels, exact, inferred, back, observation_kb_key(observation))
    return passed


def drag_drop_regression_self_check() -> bool:
    ocr_text = (
        "Please drag and drop the number 75 into the square box:\n"
        "89 75 95\nNext\nPrivacy Policy"
    )
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="drag",
        ocr_text=ocr_text, ui_nodes=[
            {"id": 9, "text": "Next", "content_desc": "", "class": "Button",
             "bounds": [80, 2300, 1360, 2500], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ], kb={}, persona={}, screen_phase="navigation", survey_tiles=[],
    )
    _DRAG_DONE.pop("done", None)
    first = drag_drop_decision(observation)
    _DRAG_DONE["done"] = True
    second = drag_drop_decision(observation)
    _DRAG_DONE.pop("done", None)
    passed = bool(
        drag_drop_question_visible(ocr_text)
        and drag_drop_target_value(ocr_text) == "75"
        and not matrix_grid_visible(observation)
        and first and first.get("action") == "drag"
        and first.get("gesture_start") and first.get("gesture_end")
        and first.get("gesture_start") != first.get("gesture_end")
        and second and second.get("action") == "click"
        and "next" in str(second.get("target_text") or "").lower()
    )
    if passed:
        logger.info("[SELF-CHECK] Drag-and-drop 75 into box then Next checks passed.")
    else:
        logger.error("[SELF-CHECK] Drag-drop failed first=%s second=%s", first, second)
    return passed


def captcha_code_regression_self_check() -> bool:
    ocr_text = (
        "Please type the following code in the text box:\n"
        "muekRw\nNext\nPrivacy Policy\nEnglish (US)"
    )
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="captcha",
        ocr_text=ocr_text, ui_nodes=[
            {"id": 9, "text": "Next", "content_desc": "", "class": "Button",
             "bounds": [80, 1480, 1360, 1680], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ], kb={}, persona={}, screen_phase="navigation", survey_tiles=[],
    )
    _CAPTCHA_TYPED.pop("captcha_code", None)
    first = captcha_code_decision(observation)
    _CAPTCHA_TYPED["captcha_code"] = "muekRw"
    second = captcha_code_decision(observation)
    repaired = prefer_progression_over_repeat(dict(second), observation)
    _CAPTCHA_TYPED.pop("captcha_code", None)
    empty = captcha_code_decision(observation)
    passed = bool(
        captcha_code_question_visible(ocr_text)
        and not matrix_grid_visible(observation)
        and first and first.get("action") == "type_text"
        and first.get("input_payload") == "muekRw"
        and second and second.get("action") == "click"
        and "next" in str(second.get("target_text") or "").lower()
        and second.get("target_coords")
        and repaired and "next" in str(repaired.get("target_text") or "").lower()
        and empty and empty.get("action") == "type_text"
        and repaired.get("action") != "back"
    )
    if passed:
        logger.info("[SELF-CHECK] Captcha code type-then-Next checks passed.")
    else:
        logger.error("[SELF-CHECK] Captcha failed first=%s second=%s empty=%s repaired=%s", first, second, empty, repaired)
    return passed


def open_text_min_words_regression_self_check() -> bool:
    """Role-model comment box must type 5+ words, not scroll or append junk."""
    ocr_text = (
        "What are the three things you like about your role model? "
        "Type your answer here... "
        "Please enter a response that is at least 5 words long for best results. "
        "WLeadership, Innovation, Dedication5555 Privacy Policy"
    )
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="open-text",
        ocr_text=ocr_text, ui_nodes=[], kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    decision = open_text_answer_decision(observation)
    nxt = survey_next_decision(observation)
    payload = str((decision or {}).get("input_payload") or "")
    passed = bool(
        open_text_question_visible(ocr_text)
        and min_words_required(ocr_text) >= 5
        and open_text_needs_more_words(observation)
        and decision and decision.get("action") == "type_text"
        and open_text_word_count(payload) >= 5
        and "5555" not in payload
        and nxt and nxt.get("action") == "type_text"
        and "scroll" not in str(nxt.get("action") or "")
    )
    filled_ocr = (
        "What are the three things you like about your role model?\n"
        "I admire my role models leadership, innovation, and dedication "
        "to helping other people succeed.\n"
        "Next\nPrivacy Policy\nEnglish (US)\nq w e r t y u i o p"
    )
    filled = Observation(
        step=1, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="open-next",
        ocr_text=filled_ocr, ui_nodes=[
            {"id": 9, "text": "Next", "content_desc": "", "class": "Button",
             "bounds": [80, 1480, 1360, 1680], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ], kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    filled_decision = open_text_answer_decision(filled)
    next_ok = bool(
        filled_decision
        and filled_decision.get("action") == "click"
        and "next" in str(filled_decision.get("target_text") or "").lower()
        and filled_decision.get("action") != "scroll_down"
    )
    passed = bool(passed and next_ok)
    if passed:
        logger.info("[SELF-CHECK] Open-text min-word sentence routing checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Open-text failed: decision=%s next=%s payload=%r filled=%s",
            decision, nxt, payload, filled_decision,
        )
    return passed


def matrix_grid_regression_self_check() -> bool:
    """Fill one transportation-matrix row per cycle, then Continue."""
    ocr_text = (
        "Over the next set of questions we will focus on transportation and mobility\n"
        "Select one for each option\n"
        "No, I have never used\n"
        "Yes, more than 3 years ago\n"
        "Yes, 1-3 years ago\n"
        "Yes, within the past 12 months\n"
        "Personal Vehicles\n"
        "Personal car (non-electric)\n"
        "Personal electric car\n"
        "Personal bicycle\n"
        "Rented a truck\n"
        "Continue »"
    )
    nodes = [
        {
            "id": 1, "text": "Personal car (non-electric)", "content_desc": "",
            "class": "TextView", "bounds": [40, 980, 420, 1080],
            "clickable": False, "checkable": False, "checked": False,
            "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 2, "text": "Personal electric car", "content_desc": "",
            "class": "TextView", "bounds": [40, 1140, 420, 1240],
            "clickable": False, "checkable": False, "checked": False,
            "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 99, "text": "Continue »", "content_desc": "", "class": "Button",
            "bounds": [700, 2800, 1120, 2940], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
    ]
    node_id = 10
    for y, _label in ((1030, "car"), (1190, "electric"), (1350, "bike"), (1510, "truck")):
        for x in (560, 780, 1000, 1220):
            nodes.append({
                "id": node_id, "text": "", "content_desc": "", "class": "RadioButton",
                "bounds": [x, y, x + 70, y + 70], "clickable": True, "checkable": False,
                "checked": False, "editable": False, "enabled": True, "selected": False,
            })
            node_id += 1
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="matrix-transport",
        ocr_text=ocr_text, ui_nodes=nodes, kb={}, persona={},
        screen_phase=classify_screen_phase(ocr_text, nodes), survey_tiles=[],
    )
    reset_matrix_session()
    first = configured_matrix_decision(observation)
    if first and first.get("matrix_row_label"):
        _MATRIX_SESSION.setdefault("done", []).append(
            str(first.get("matrix_row_key") or first.get("matrix_row_label"))
        )
    second = configured_matrix_decision(observation)
    truncated = parse_json_response(
        '{"screen_state":"navigation","action":"click","target_text":"No, I have never used","selection_complete":'
    )
    passed = bool(
        observation.screen_phase == "survey_question"
        and matrix_question(observation)
        and first
        and first.get("action") == "select_matrix_cell"
        and "car" in str(first.get("row_text") or "").lower()
        and "12 month" in str(first.get("column_text") or "").lower()
        and second
        and second.get("action") == "select_matrix_cell"
        and "electric" in str(second.get("row_text") or "").lower()
        and "never" in str(second.get("column_text") or "").lower()
        and truncated.get("target_text") == "No, I have never used"
        and choose_matrix_column("Rented a truck", [
            "No, I have never used", "Yes, more than 3 years ago",
            "Yes, 1-3 years ago", "Yes, within the past 12 months",
        ]) == "No, I have never used"
        and "12 month" in choose_matrix_column("Personal car (non-electric)", [
            "No, I have never used", "Yes, more than 3 years ago",
            "Yes, 1-3 years ago", "Yes, within the past 12 months",
        ]).lower()
        and "12 month" in str(first.get("column_text") or "").lower()
    )
    reset_matrix_session()
    if passed:
        logger.info("[SELF-CHECK] Matrix grid one-row-per-cycle checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Matrix grid routing failed: phase=%s first=%s second=%s",
            observation.screen_phase, first, second,
        )
    return passed
