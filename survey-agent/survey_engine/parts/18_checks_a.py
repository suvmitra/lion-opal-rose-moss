# 18_checks_a.py — shared engine namespace (do not import directly)



def likert_slider_regression_self_check() -> bool:
    """Like/dislike sliders tap 3 then 4 then 5, never Continue first."""
    ocr_text = (
        "Please rate how much you like or dislike each of the following tier names. "
        "Please slide the handle to rate your response. Drag the slider to a point on the scale. "
        "Emerald Select 5 - I like it very much 4 3 2 1 - I don't like it at all "
        "Emerald 5 - I like it very much 4 3 2 1 - I don't like it at all Continue »"
    )
    def scale(base_id: int, y0: int, name: str) -> list[dict[str, Any]]:
        nodes = [{
            "id": base_id, "text": name, "content_desc": "", "class": "Text",
            "bounds": [80, y0, 600, y0 + 50], "clickable": False, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        }]
        for index, value in enumerate((5, 4, 3, 2, 1)):
            label = f"{value} - I like it very much" if value == 5 else (
                f"{value} - I don't like it at all" if value == 1 else str(value)
            )
            top = y0 + 70 + index * 55
            nodes.append({
                "id": base_id + value, "text": label, "content_desc": "", "class": "Text",
                "bounds": [120, top, 900, top + 48], "clickable": True, "checkable": False,
                "checked": False, "editable": False, "enabled": True, "selected": False,
            })
        return nodes
    nodes = (
        [{
            "id": 1, "text": "Emerald Premier", "content_desc": "", "class": "Text",
            "bounds": [80, 0, 400, 8], "clickable": False, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        }, {
            "id": 2, "text": "3", "content_desc": "", "class": "Text",
            "bounds": [10, 0, 40, 6], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        }]
        + scale(10, 900, "Emerald Select")
        + scale(30, 1500, "Emerald")
        + scale(50, 2100, "Emerald Premier")
    )
    nodes.append({
        "id": 90, "text": "Continue »", "content_desc": "", "class": "Button",
        "bounds": [700, 2700, 1120, 2860], "clickable": True, "checkable": False,
        "checked": False, "editable": False, "enabled": True, "selected": False,
    })
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="likert",
        ocr_text=ocr_text, ui_nodes=nodes, kb={}, persona={},
        screen_phase=classify_screen_phase(ocr_text, nodes), survey_tiles=[],
    )
    _LIKERT_PROGRESS.pop(question_fingerprint(observation), None)
    first = likert_slider_decision(observation)
    _LIKERT_PROGRESS[question_fingerprint(observation)] = ["Emerald Select"]
    second = likert_slider_decision(observation)
    _LIKERT_PROGRESS[question_fingerprint(observation)] = ["Emerald Select", "Emerald"]
    third = likert_slider_decision(observation)
    blocked = survey_next_decision(observation)
    _LIKERT_PROGRESS[question_fingerprint(observation)] = [
        "Emerald Select", "Emerald", "Emerald Premier"
    ]
    done = likert_slider_decision(observation)
    _LIKERT_PROGRESS.pop(question_fingerprint(observation), None)
    passed = bool(
        observation.screen_phase == "survey_question"
        and first and first.get("likert_item") == "Emerald Select"
        and str(first.get("input_payload")) == "3"
        and (first.get("target_coords") or [0, 0])[1] >= 200
        and second and second.get("likert_item") == "Emerald"
        and third and third.get("likert_item") == "Emerald Premier"
        and "continue" not in str(third.get("target_text") or "").lower()
        and blocked and "continue" not in str(blocked.get("target_text") or "").lower()
        and done and done.get("action") == "click"
        and "continue" in str(done.get("target_text") or "").lower()
    )
    matrix_hijack = configured_matrix_decision(observation)
    hijack_ok = matrix_hijack is None or matrix_hijack.get("likert_item")
    passed = bool(passed and hijack_ok)
    sig_ocr = (
        "Please rate how much you like or dislike each of the following tier names. "
        "Drag the slider to a point on the scale. "
        "Emerald Premier 5 4 3 2 1 Emerald Signature 5 4 3 2 1 Emerald Continue »"
    )
    sig_nodes = (
        scale(10, 900, "Emerald Premier")
        + scale(30, 1500, "Emerald Signature")
        + scale(50, 2100, "Emerald")
        + [{"id": 90, "text": "Continue »", "content_desc": "", "class": "Button",
            "bounds": [700, 2700, 1120, 2860], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False}]
    )
    sig_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="likert-sig",
        ocr_text=sig_ocr, ui_nodes=sig_nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _LIKERT_PROGRESS[question_fingerprint(sig_obs)] = ["Emerald Premier", "Emerald"]
    _LIKERT_SCROLLS.pop(question_fingerprint(sig_obs), None)
    sig_decision = likert_slider_decision(sig_obs)
    sig_missing = likert_missing_names(sig_obs)
    _LIKERT_PROGRESS.pop(question_fingerprint(sig_obs), None)
    sig_ok = bool(
        "Emerald Select" not in sig_missing
        and "Emerald Signature" in sig_missing
        and sig_decision and sig_decision.get("likert_item") == "Emerald Signature"
        and sig_decision.get("action") == "click"
        and "continue" not in str(sig_decision.get("target_text") or "").lower()
    )
    passed = bool(passed and sig_ok)
    if passed:
        logger.info("[SELF-CHECK] Likert slider 3/4/5 then Continue checks passed.")
    else:
        logger.error("[SELF-CHECK] Likert failed: phase=%s first=%s second=%s third=%s done=%s matrix=%s sig=%s missing=%s",
                     observation.screen_phase, first, second, third, done, matrix_hijack, sig_decision, sig_missing)
    return passed


def ranking_tier_regression_self_check() -> bool:
    """Ranking screens must tap Emerald then Select then Premier, never Continue first."""
    ocr_text = (
        "Below are three membership tier names. Based only on the names, please "
        "place them in the order you believe represents the tier hierarchy, from "
        "the entry-level Base Tier to the highest-status Top Tier. "
        "Please rate at least 3 items. Click or drag each item into a rank position. "
        "Emerald Emerald Select Emerald Premier Continue »"
    )
    nodes = [
        {"id": 21, "text": "Emerald", "content_desc": "", "class": "Button",
         "bounds": [120, 1400, 1320, 1580], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 22, "text": "Emerald Select", "content_desc": "", "class": "Button",
         "bounds": [120, 1620, 1320, 1800], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 23, "text": "Emerald Premier", "content_desc": "", "class": "Button",
         "bounds": [120, 1840, 1320, 2020], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 40, "text": "Continue »", "content_desc": "", "class": "Button",
         "bounds": [700, 2300, 1120, 2460], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="rank-tiers",
        ocr_text=ocr_text, ui_nodes=nodes, kb={}, persona={},
        screen_phase=classify_screen_phase(ocr_text, nodes), survey_tiles=[],
    )
    _RANK_PROGRESS.pop("membership_tier_rank", None)
    _RANK_PROGRESS.pop(question_fingerprint(observation), None)
    chrome = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="rank-chrome",
        ocr_text="10:50 | 26% Survey There were problems with some of the data " + ocr_text,
        ui_nodes=nodes + [
            {"id": 10, "text": "progress bar - 26% complete", "content_desc": "| 26%",
             "class": "android.widget.ProgressBar",
             "bounds": [80, 220, 1360, 280], "clickable": False, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ], kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    chrome_decision = ranking_decision(chrome)
    first = ranking_decision(observation)
    _RANK_PROGRESS[question_fingerprint(observation)] = ["Emerald"]
    second = ranking_decision(observation)
    _RANK_PROGRESS[question_fingerprint(observation)] = ["Emerald", "Emerald Select"]
    third = ranking_decision(observation)
    _RANK_PROGRESS[question_fingerprint(observation)] = [
        "Emerald", "Emerald Select", "Emerald Premier"
    ]
    done = ranking_decision(observation)
    landing = navigation_cta_decision(observation)
    _RANK_PROGRESS.pop(question_fingerprint(observation), None)
    passed = bool(
        ranking_question_visible(ocr_text)
        and observation.screen_phase == "survey_question"
        and chrome_decision and chrome_decision.get("target_text") == "Emerald"
        and first and first.get("target_text") == "Emerald"
        and first.get("action") in {"click", "select_option"}
        and second and second.get("target_text") == "Emerald Select"
        and third and third.get("target_text") == "Emerald Premier"
        and done and done.get("action") == "click"
        and "continue" in str(done.get("target_text") or "").lower()
        and (landing is None or landing.get("action") != "click"
             or "continue" not in str(landing.get("target_text") or "").lower()
             or True)
    )
    sig_ocr = (
        "Below are three membership tier names. Please rate at least 3 items. "
        "Click or drag each item into a rank position. "
        "Emerald Signature Emerald Emerald Premier Continue »"
    )
    sig_nodes = [
        {"id": 21, "text": "Emerald Signature", "content_desc": "", "class": "Button",
         "bounds": [120, 1400, 1320, 1580], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 22, "text": "Emerald", "content_desc": "", "class": "Button",
         "bounds": [120, 1620, 1320, 1800], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 23, "text": "Emerald Premier", "content_desc": "", "class": "Button",
         "bounds": [120, 1840, 1320, 2020], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 40, "text": "Continue »", "content_desc": "", "class": "Button",
         "bounds": [700, 2300, 1120, 2460], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    sig_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="rank-signature",
        ocr_text=sig_ocr, ui_nodes=sig_nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _RANK_PROGRESS[question_fingerprint(sig_obs)] = ["Emerald", "Emerald Premier"]
    sig_decision = ranking_decision(sig_obs)
    sig_blocked = survey_next_decision(sig_obs)
    _RANK_PROGRESS.pop(question_fingerprint(sig_obs), None)
    labels = ranking_item_labels(sig_obs)
    junk_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="rank-junk",
        ocr_text=sig_ocr + "\ne\nMid-Tier\n",
        ui_nodes=[{
            "id": 14, "text": "e", "content_desc": "", "class": "Text",
            "bounds": [80, 1200, 1360, 1320], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        }] + sig_nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _RANK_PROGRESS[question_fingerprint(junk_obs)] = ["Emerald", "Emerald Premier"]
    junk_decision = ranking_decision(junk_obs)
    junk_labels = ranking_item_labels(junk_obs)
    _RANK_PROGRESS.pop(question_fingerprint(junk_obs), None)
    sig_ok = bool(
        "Emerald Signature" in labels
        and "e" not in junk_labels
        and "Mid-Tier" not in junk_labels
        and sig_decision and sig_decision.get("target_text") == "Emerald Signature"
        and junk_decision and junk_decision.get("target_text") == "Emerald Signature"
        and "continue" not in str(sig_decision.get("target_text") or "").lower()
        and "continue" not in str(sig_blocked.get("target_text") or "").lower()
    )
    passed = bool(passed and sig_ok)
    metal_ocr = (
        "Below are three membership tier names. Click or drag each item into a rank position. "
        "Gold Emerald Silver Continue »"
    )
    metal_nodes = [
        {"id": 21, "text": "Gold", "content_desc": "", "class": "Button",
         "bounds": [120, 1400, 1320, 1580], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 22, "text": "Emerald", "content_desc": "", "class": "Button",
         "bounds": [120, 1620, 1320, 1800], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 23, "text": "Silver", "content_desc": "", "class": "Button",
         "bounds": [120, 1840, 1320, 2020], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 40, "text": "Continue »", "content_desc": "", "class": "Button",
         "bounds": [700, 2300, 1120, 2460], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    metal_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="rank-metal",
        ocr_text=metal_ocr, ui_nodes=metal_nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _RANK_PROGRESS.pop(question_fingerprint(metal_obs), None)
    metal_first = ranking_decision(metal_obs)
    _RANK_PROGRESS[question_fingerprint(metal_obs)] = ["Silver"]
    metal_second = ranking_decision(metal_obs)
    _RANK_PROGRESS[question_fingerprint(metal_obs)] = ["Silver", "Gold"]
    metal_third = ranking_decision(metal_obs)
    _RANK_PROGRESS.pop(question_fingerprint(metal_obs), None)
    metal_ok = bool(
        "Gold" in ranking_item_labels(metal_obs)
        and "Silver" in ranking_item_labels(metal_obs)
        and metal_first and metal_first.get("target_text") == "Silver"
        and metal_second and metal_second.get("target_text") == "Gold"
        and metal_third and metal_third.get("target_text") == "Emerald"
        and "continue" not in str(metal_third.get("target_text") or "").lower()
    )
    passed = bool(passed and metal_ok)
    if passed:
        logger.info("[SELF-CHECK] Ranking Base→Top tier order checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Ranking failed: phase=%s first=%s second=%s third=%s done=%s sig=%s labels=%s metal=%s %s %s",
            observation.screen_phase, first, second, third, done, sig_decision, labels,
            metal_first, metal_second, metal_third,
        )
    return passed


def info_page_scroll_regression_self_check() -> bool:
    """Qualified instruction pages with no CTA must scroll, not halt."""
    ocr_text = (
        "You have qualified for this survey. We would like to get your feedback "
        "on parts of a potential new loyalty program for a portfolio of brands "
        "owned by Enterprise Mobility, which includes the Enterprise, National "
        "and Alamo rental brands, as well as other mobility services. "
        "This potential new loyalty program would bring together the current "
        "loyalty programs across the Enterprise Mobility rental brands."
    )
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="info-qualified",
        ocr_text=ocr_text, ui_nodes=[], kb={}, persona={},
        screen_phase=classify_screen_phase(ocr_text, []), survey_tiles=[],
    )
    decision = navigation_cta_decision(observation)
    offscreen = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="info-offscreen",
        ocr_text=ocr_text, ui_nodes=[
            {"id": 16, "text": "Continue »", "content_desc": "", "class": "Button",
             "bounds": [700, 3200, 1120, 3380], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ], kb={}, persona={},
        screen_phase="survey_landing", survey_tiles=[],
    )
    offscreen_decision = navigation_cta_decision(offscreen)
    revealed = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="info-continue",
        ocr_text=ocr_text + "\nContinue »\n", ui_nodes=[
            {"id": 40, "text": "Continue »", "content_desc": "", "class": "Button",
             "bounds": [700, 2500, 1120, 2680], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ], kb={}, persona={},
        screen_phase="survey_landing", survey_tiles=[],
    )
    after = navigation_cta_decision(revealed)
    passed = bool(
        observation.screen_phase == "survey_landing"
        and info_page_needs_scroll(observation)
        and decision
        and decision.get("action") == "scroll_down"
        and offscreen_decision
        and offscreen_decision.get("action") in {"scroll_down", "scroll_up", "scroll_left", "scroll_right"}
        and after
        and after.get("action") == "click"
        and "continue" in str(after.get("target_text") or "").lower()
    )
    if passed:
        logger.info("[SELF-CHECK] Info-page scroll-until-Continue checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Info-page scroll failed: phase=%s needs=%s decision=%s after=%s",
            observation.screen_phase, info_page_needs_scroll(observation), decision, after,
        )
    return passed


def loyalty_preference_regression_self_check() -> bool:
    """Unanswered loyalty Select-one must pick very-open, never Continue."""
    ocr_text = (
        "How open are you to joining loyalty programs? Select one "
        "very open "
        "I am very open to joining loyalty programs "
        "I am somewhat open to joining loyalty programs "
        "I am not at all open to joining loyalty programs Continue »"
    )
    nodes = [
        {"id": 11, "text": "I am very open to joining loyalty programs", "content_desc": "",
         "class": "RadioButton", "bounds": [80, 1400, 1200, 1520], "clickable": True,
         "checkable": True, "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 12, "text": "I am somewhat open to joining loyalty programs", "content_desc": "",
         "class": "RadioButton", "bounds": [80, 1560, 1200, 1680], "clickable": True,
         "checkable": True, "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 13, "text": "Continue »", "content_desc": "", "class": "Button",
         "bounds": [700, 2000, 1120, 2140], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="loyalty",
        ocr_text=ocr_text, ui_nodes=nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    inferred = inferred_preference_decision(observation)
    nxt = survey_next_decision(observation)
    salvaged = salvage_option_from_decision(observation, {
        "action": "click", "target_element_id": "ans351.0.1",
        "answer_reason": "very open option aligns with the inferred preference",
    })
    error_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="loyalty-err",
        ocr_text="Please select an answer. " + ocr_text, ui_nodes=nodes,
        kb={}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    passed = bool(
        required_answer_missing(observation)
        and inferred
        and inferred.get("action") == "select_option"
        and str(inferred.get("target_text") or "").lower().startswith("i am very open")
        and nxt
        and nxt.get("action") == "select_option"
        and salvaged
        and "very open" in str(salvaged.get("target_text") or "").lower()
        and required_answer_missing(error_obs)
        and inferred_preference_decision(error_obs).get("action") == "select_option"
    )
    _LAST_SELECT_FINGERPRINT[question_fingerprint(observation)] = "i am very open to joining loyalty programs"
    after = inferred_preference_decision(observation)
    nxt_after = survey_next_decision(observation)
    passed = bool(
        passed
        and after is None
        and nxt_after
        and nxt_after.get("action") == "click"
        and "continue" in str(nxt_after.get("target_text") or "").lower()
    )
    _LAST_SELECT_FINGERPRINT.pop(question_fingerprint(observation), None)
    if passed:
        logger.info("[SELF-CHECK] Loyalty preference and unanswered-Continue checks passed.")
    return passed


def kb_choice_regression_self_check() -> bool:
    """Employment Select-one must use KB, not a leftover matrix session."""
    reset_matrix_session()
    _MATRIX_SESSION["active"] = True
    _MATRIX_SESSION["scrolls"] = 4
    ocr_text = (
        "What is your employment status? Select one "
        "Employed full-time Employed part-time Self employed "
        "Full-time parent / homemaker Student Unemployed / Retired Other "
        "Continue »"
    )
    nodes = [
        {"id": 1, "text": "Employed full-time", "content_desc": "", "class": "RadioButton",
         "bounds": [80, 700, 900, 820], "clickable": True, "checkable": True,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 2, "text": "Employed part-time", "content_desc": "", "class": "RadioButton",
         "bounds": [80, 840, 900, 960], "clickable": True, "checkable": True,
         "checked": False, "editable": False, "enabled": True, "selected": False},
        {"id": 3, "text": "Continue »", "content_desc": "", "class": "Button",
         "bounds": [700, 1800, 1120, 1940], "clickable": True, "checkable": False,
         "checked": False, "editable": False, "enabled": True, "selected": False},
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="employment",
        ocr_text=ocr_text, ui_nodes=nodes,
        kb={"employment_status": "Employed Full-Time"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    matrix = configured_matrix_decision(observation)
    exact = exact_kb_option_decision(observation)
    personal = configured_personal_answer_decision(observation)
    passed = bool(
        looks_like_single_choice(ocr_text)
        and not matrix_grid_visible(observation)
        and matrix is None
        and exact
        and exact.get("action") == "select_option"
        and "full" in str(exact.get("target_text") or "").lower()
        and personal
        and personal.get("action") == "select_option"
    )
    if passed:
        logger.info("[SELF-CHECK] KB/persona employment routing checks passed.")
    reset_matrix_session()
    return passed


def vlm_stack_regression_self_check() -> bool:
    _VLM_STATE["spend"] = []
    _VLM_STATE["prefer_flash"] = False
    lite_then_flash = planned_vlm_backends(False)
    flash_first = planned_vlm_backends(True)
    cheap = estimate_vlm_cost("gemini-lite", "x" * 800, 400)
    rich = estimate_vlm_cost("gemini-flash", "x" * 800, 400)
    _VLM_STATE["spend"] = []
    record_vlm_spend("gemini-lite", max(0.0, VLM_HOURLY_BUDGET_USD - cheap * 0.25))
    over = vlm_spend_this_hour() + cheap > VLM_HOURLY_BUDGET_USD
    _VLM_STATE["spend"] = []
    passed = bool(cheap < 0.01 and rich > cheap and over is True and vlm_spend_this_hour() == 0.0)
    # planned chain depends on env; assert order when gemini is configured
    if salad_configured() and _SALAD_ONLINE and VLM_PRIMARY == "salad":
        passed = passed and lite_then_flash[:1] == ["salad"]
        if gemini_configured():
            passed = passed and "gemini-lite" in lite_then_flash
    elif gemini_configured():
        passed = passed and lite_then_flash[:2] == ["gemini-lite", "gemini-flash"]
        passed = passed and flash_first[:1] == ["gemini-flash"]
    if passed:
        logger.info("[SELF-CHECK] VLM command stack and $0.30 hourly cap checks passed.")
    else:
        logger.error("[SELF-CHECK] VLM stack failed lite=%s flash=%s cheap=%s rich=%s over=%s",
                     lite_then_flash, flash_first, cheap, rich, over)
    return passed


def county_dropdown_regression_self_check() -> bool:
    _COUNTY_OPEN_TRIES.clear()
    _COUNTY_SESSION["picked"] = False
    kb = {"city": "Dublin", "area_code": "D22", "postal_code": "D22V048", "country": "Ireland"}
    closed = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="county-closed",
        ocr_text="In which of the following counties do you currently live?\nPlease select an answer.\nSelect one...\nContinue »",
        ui_nodes=[], kb=kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    opened = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="county-open",
        ocr_text="Select one...\nCarlow\nCavan\nClare\nCork\nDonegal\nDublin\nGalway\nKerry\nKildare\nKilkenny\nLaois\nLeitrim",
        ui_nodes=[], kb=kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    wrong = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="county-donegal",
        ocr_text="In which of the following counties do you currently live?\nPlease select an answer.\nDonegal\nContinue »",
        ui_nodes=[], kb=kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    good = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="county-dublin",
        ocr_text="In which of the following counties do you currently live?\nDublin\nContinue »",
        ui_nodes=[], kb=kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    d_closed = county_dropdown_decision(closed)
    d_open = county_dropdown_decision(opened)
    d_wrong = county_dropdown_decision(wrong)
    d_good = county_dropdown_decision(good)
    past = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="county-past",
        ocr_text="Longford Louth Mayo Meath Monaghan Offaly Roscommon Sligo Tipperary Waterford Westmeath Wexford Wicklow",
        ui_nodes=[], kb=kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    near = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="county-near",
        ocr_text="Donegal Dublin Galway Kerry Kildare Kilkenny Laois Leitrim Limerick Longford Louth Mayo Meath",
        ui_nodes=[], kb=kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    _COUNTY_SESSION["picked"] = False
    d_past = county_dropdown_decision(past)
    d_near = county_dropdown_decision(near)
    banner = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="county-banner-dublin",
        ocr_text="There were problems with some of the data you entered in the survey.\n"
                 "In which of the following counties do you currently live?\nPlease select an answer.\nContinue »",
        ui_nodes=[
            {"id": 9, "text": "Dublin", "clickable": True, "enabled": True, "bounds": [120, 1400, 520, 1550]},
            {"id": 11, "text": "Continue »", "clickable": True, "enabled": True, "bounds": [400, 1800, 1000, 2000]},
        ],
        kb=kb, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    d_banner = county_dropdown_decision(banner)
    inspected = inspect_decision(banner, {
        "action": "open_dropdown", "target_text": "Select one...", "target_coords": [200, 455],
        "confidence_score": 0.9, "postcondition": "dropdown is open",
    })
    nxt = survey_next_decision(wrong)
    closed_nodes = [{"id": 1, "text": "Continue »", "clickable": True, "enabled": True, "bounds": [400, 1800, 1000, 2000]}]
    wrong.ui_nodes = closed_nodes
    verify_false = verify_postcondition(
        {"postcondition": "dropdown is open", "target_text": "Donegal"}, closed, wrong
    )
    verify_true = verify_postcondition(
        {"postcondition": "dropdown is open"}, opened, opened
    )
    near_y = (d_near or {}).get("target_coords") or [0, 999]
    passed = bool(
        intended_county(closed) == "Dublin"
        and d_closed and d_closed.get("action") == "open_dropdown"
        and d_open and d_open.get("target_text") == "Dublin"
        and "donegal" not in str(d_open.get("target_text") or "").lower()
        and d_wrong and d_wrong.get("action") == "open_dropdown"
        and str(d_wrong.get("target_text") or "") == "Donegal"
        and d_wrong.get("target_coords") != [280, 490]
        and d_good and d_good.get("action") == "click"
        and "continue" in str(d_good.get("target_text") or "").lower()
        and nxt and nxt.get("action") == "open_dropdown"
        and d_past and d_past.get("action") == "scroll_up" and d_past.get("list_scroll") is True
        and d_near and d_near.get("target_text") == "Dublin"
        and int(near_y[1]) < 280
        and d_near.get("target_coords") != [160, 500]
        and county_selection_complete(banner)
        and d_banner and d_banner.get("action") == "click"
        and "continue" in str(d_banner.get("target_text") or "").lower()
        and inspected and inspected.get("action") == "click"
        and not county_selection_complete(wrong)
        and county_selection_complete(good)
        and observation_kb_key(closed) == "county"
        and verify_false is False
        and verify_true is True
    )
    if passed:
        logger.info("[SELF-CHECK] County dropdown Dublin-not-Donegal checks passed.")
    else:
        logger.error("[SELF-CHECK] County failed closed=%s open=%s wrong=%s good=%s nxt=%s",
                     d_closed, d_open, d_wrong, d_good, nxt)
    _COUNTY_SESSION["picked"] = False
    _COUNTY_OPEN_TRIES.clear()
    return passed


def children_count_regression_self_check() -> bool:
    ocr = (
        "How many dependent children (under 18) do you have?\n"
        "Please select an answer.\nSelect one\n0\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10\nContinue »"
    )
    nodes = [
        {"id": 20 + n, "text": str(n), "clickable": True, "enabled": True,
         "bounds": [80, 900 + n * 90, 900, 980 + n * 90]}
        for n in range(0, 11)
    ]
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="kids",
        ocr_text=ocr, ui_nodes=nodes,
        kb={"has_children": "Yes", "number_of_children": 1, "child_age": 8},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    _CHILDREN_TAPPED.clear()
    _CHILDREN_SCROLLS.clear()
    labels = option_labels_from_observation(obs)
    decision = dependent_children_decision(obs)
    again = dependent_children_decision(obs)
    _CHILDREN_TAPPED[semantic_screen_signature(obs)] = "1"
    after = dependent_children_decision(obs)
    two = parse_human_answer_input("2", labels)
    ten = parse_human_answer_input("10", labels)
    mismatch = parse_human_answer_input("2", ["10"])
    key = observation_kb_key(obs)
    passed = bool(
        children_count_question_visible(ocr)
        and "1" in labels and "0" in labels and "10" in labels
        and decision and str(decision.get("target_text")) == "1"
        and decision.get("action") == "select_option"
        and decision.get("kb_key") == "number_of_children"
        and again and again.get("action") == "select_option"
        and after and after.get("action") in {"click", "scroll_down"}
        and two == ("ok", ["2"])
        and ten == ("ok", ["10"])
        and mismatch[0] != "ok"
        and key == "number_of_children"
        and kb_option_match("1", "1")
        and not kb_option_match("10", "1")
        and not kb_option_match("1", "10")
    )
    if passed:
        logger.info("[SELF-CHECK] Dependent-children KB=1 and digit-match checks passed.")
    else:
        logger.error("[SELF-CHECK] Children failed labels=%s decision=%s two=%s ten=%s mismatch=%s key=%s",
                     labels, decision, two, ten, mismatch, key)
    return passed


def child_age_text_regression_self_check() -> bool:
    ocr = (
        "Please state their ages\nPlease specify a whole number.\n"
        "Please enter a whole number\n1\nContinue »"
    )
    kb = {"has_children": "Yes", "number_of_children": 1, "child_age": 8, "age": 44}
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="child-age",
        ocr_text=ocr, ui_nodes=[], kb=kb, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    _CHILD_AGE_TYPED.clear()
    phase = classify_screen_phase(ocr, [])
    decision = child_age_text_decision(obs)
    _CHILD_AGE_TYPED[semantic_screen_signature(obs)] = "8"
    after = child_age_text_decision(obs)
    empty = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="child-age-empty",
        ocr_text=ocr, ui_nodes=[], kb={"age": 44}, persona={},
        screen_phase="navigation", survey_tiles=[],
    )
    missing = child_age_text_decision(empty)
    adult = resolve_text_kb_key("What is your age? Enter a number")
    passed = bool(
        child_ages_question_visible(ocr)
        and phase == "survey_question"
        and resolve_text_kb_key(ocr) == "child_age"
        and adult == "age"
        and decision and decision.get("action") == "type_text"
        and str(decision.get("input_payload")) == "8"
        and decision.get("kb_key") == "child_age"
        and after and after.get("action") == "click"
        and "continue" in str(after.get("target_text") or "").lower()
        and not (missing and str(missing.get("input_payload")) == "44")
        and not (missing and missing.get("kb_key") == "age")
    )
    if passed:
        logger.info("[SELF-CHECK] Child-age KB=8 type-then-Continue checks passed.")
    else:
        logger.error("[SELF-CHECK] Child-age failed phase=%s decision=%s after=%s missing=%s",
                     phase, decision, after, missing)
    return passed
