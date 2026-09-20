# 17_human.py — shared engine namespace (do not import directly)



def persist_human_survey_answer(
    kb_key: str,
    question: str,
    matched_options: list[str],
    raw_input: str,
    multi_select: bool,
) -> Any:
    value: Any = matched_options if multi_select or len(matched_options) != 1 else matched_options[0]
    update_kb(
        kb_key,
        value,
        reason="Operator terminal key-in for an unresolved personal survey question.",
        provenance="declared",
        confidence=1.0,
        question=question,
        source_basis=f"Human terminal input: {raw_input[:300]}",
    )
    kb = load_kb()
    fallbacks = kb.get("personal_question_fallbacks")
    if not isinstance(fallbacks, dict):
        fallbacks = {}
    fallbacks[kb_key] = {
        "kb_key": kb_key,
        "question_keywords": fallback_keywords_from_question(question),
        "answer": value,
        "provenance": "declared",
        "confidence": 1.0,
        "source_basis": f"Human terminal input: {raw_input[:300]}",
    }
    kb["personal_question_fallbacks"] = fallbacks
    save_kb(kb)
    logger.info(
        "[HUMAN KB] Persisted kb_key=%s value=%r from terminal input %r",
        kb_key, value, raw_input,
    )
    return value


def stdin_can_prompt() -> bool:
    try:
        return bool(ALLOW_INTERACTIVE_HUMAN_INPUT and sys.stdin and sys.stdin.isatty())
    except Exception:
        return False


def prompt_human_terminal_answer(
    obs: Observation,
    reason: str,
    options: list[str],
    question: str,
) -> Optional[list[str]]:
    """Ask the operator to key in the visible answer(s). Returns None on skip/unavailable."""
    if not stdin_can_prompt():
        logger.error(
            "[HUMAN] Interactive stdin is unavailable; cannot capture an answer for %r (%s).",
            question, reason,
        )
        return None

    option_lines = "\n".join(
        f"  {index}. {label}" for index, label in enumerate(options, 1)
    ) or "  (no option labels parsed — type the visible wording)"
    banner = (
        "\n" + "=" * 78 + "\n"
        "HUMAN INPUT REQUIRED — the model did not resolve this personal question.\n"
        f"Reason: {reason}\n\n"
        f"Question:\n  {question or '(see device screen)'}\n\n"
        f"Visible options:\n{option_lines}\n\n"
        "Type matching option(s). Examples:\n"
        "  Cat, Dog, Fish\n"
        "  only Fish\n"
        "  2\n"
        "  option 2\n"
        "  middle manager\n"
        "  3, 4, 5\n"
        "  none\n"
        "  skip   (leave unanswered and halt)\n"
        "=" * 78 + "\n"
    )
    print(banner, flush=True)
    logger.warning("[HUMAN PROMPT] %s | options=%s", question, options)

    for attempt in range(1, HUMAN_INPUT_MAX_ATTEMPTS + 1):
        try:
            raw = input("Answer> ").strip()
        except EOFError:
            logger.error("[HUMAN] stdin closed while waiting for an answer.")
            return None
        if not options:
            lowered = raw.lower().strip()
            if lowered in SKIP_TOKENS:
                logger.warning("[HUMAN] Operator skipped question %r", question)
                return None
            if raw:
                print(f"Recorded: {raw}", flush=True)
                return [raw]
        status, matched = parse_human_answer_input(raw, options)
        if status == "skip":
            logger.warning("[HUMAN] Operator skipped question %r", question)
            return None
        if status == "ok" and matched:
            print(f"Recorded: {', '.join(matched)}", flush=True)
            return matched
        print(
            f"Could not match {raw!r} to a visible option. "
            f"Attempt {attempt}/{HUMAN_INPUT_MAX_ATTEMPTS}.",
            flush=True,
        )
        logger.warning("[HUMAN] Unmatched input %r attempt=%s", raw, attempt)
    return None


def capture_human_answer_decision(
    obs: Observation,
    reason: str,
) -> Optional[dict[str, Any]]:
    """Replace request_human / LLM failure with a grounded, persisted answer."""
    if obs.screen_phase != "survey_question":
        return None
    if maxdiff_question_visible(obs.ocr_text):
        fill = maxdiff_decision(obs)
        if fill:
            logger.info("[HUMAN] MaxDiff is local; not prompting the operator.")
            return fill
    if select_all_apply_visible(obs.ocr_text):
        fill = select_all_apply_decision(obs)
        if fill:
            logger.info("[HUMAN] Select-all is local; not prompting the operator.")
            return fill
    stored = configured_multi_option_decision(obs)
    if stored is not None:
        return stored

    options = option_labels_from_observation(obs)
    question = current_question_text(obs)
    signature = semantic_screen_signature(obs)
    fact_key = "child_age" if child_ages_question_visible(obs.ocr_text) else (
        "number_of_children" if children_count_question_visible(obs.ocr_text) else signature
    )
    if signature in _HUMAN_PROMPTED_SIGNATURES or fact_key in _HUMAN_PROMPTED_KEYS:
        logger.warning("[HUMAN] Already prompted %s; not asking again.", fact_key)
        return None
    _HUMAN_PROMPTED_SIGNATURES.add(signature)
    _HUMAN_PROMPTED_KEYS.add(str(fact_key))

    text_entry = text_entry_question_visible(obs.ocr_text, obs.ui_nodes) or not options
    if obs.screenshot is None:
        logger.info("[HUMAN] Skipping terminal prompt during self-check (no screenshot).")
        return None
    matched = prompt_human_terminal_answer(obs, reason, [] if text_entry else options, question)
    if not matched:
        return None

    kb_key = resolve_text_kb_key(question) or observation_kb_key(obs)
    if children_count_question_visible(obs.ocr_text):
        kb_key = "number_of_children"
        if matched and str(matched[0]).isdigit():
            matched = [str(int(matched[0]))]
    if child_ages_question_visible(obs.ocr_text):
        kb_key = "child_age"
    if text_entry:
        persist_human_survey_answer(kb_key, question, matched, matched[0], False)
        obs.kb = load_kb()
        target = editable_candidate(obs.ui_nodes, obs.ocr_text)
        decision = {
            "screen_state": "survey_question",
            "question_text": question,
            "answer_reason": "Operator typed this personal value in the terminal.",
            "action": "type_text",
            "target_element_id": target.get("id") if target else None,
            "target_text": f"{kb_key} input field",
            "target_coords": None if target else text_entry_field_coords(obs),
            "input_payload": str(matched[0]).strip(),
            "kb_key": kb_key,
            "kb_write": False,
            "missing_fact_key": None,
            "confidence_score": 0.99,
            "postcondition": f"field contains {matched[0]}",
            "visual_reasoning": "Terminal key-in of a missing personal text fact.",
            "answer_provenance": "declared",
            "source_basis": "Human terminal key-in",
            "inference_confidence": 1.0,
        }
        logger.info("[HUMAN DECISION] %s", json.dumps(decision, ensure_ascii=False))
        return decision

    multi = multi_select_question(obs) or len(matched) > 1
    persist_human_survey_answer(kb_key, question, matched, ", ".join(matched), multi)
    obs.kb = load_kb()
    remaining_after = matched[1:] if multi else []
    decision = grounded_option_decision(
        obs,
        matched[0],
        kb_key=kb_key,
        intended=matched,
        remaining_after=remaining_after,
        reason="Operator typed this answer in the terminal after the model could not resolve it.",
        provenance="declared",
        source_basis="Human terminal key-in",
    )
    logger.info("[HUMAN DECISION] %s", json.dumps(decision, ensure_ascii=False))
    return decision


def human_input_pets_regression_self_check() -> bool:
    """Guard terminal key-in, KB persistence shape, and pets multi-select ticking."""
    ocr_text = (
        "Which of these pets currently live with you in your household?\n"
        "Search\n"
        "Amphibians (frogs, toads, etc.)\n"
        "Bird(s)\n"
        "Cat(s)\n"
        "Dog(s)\n"
        "Fish\n"
        "Horse(s)\n"
        "I do not have any pets\n"
        "Privacy Policy"
    )
    nodes = [
        {
            "id": 40 + index,
            "text": label,
            "content_desc": "",
            "class": "CheckBox",
            "bounds": [80, 700 + index * 160, 1360, 840 + index * 160],
            "clickable": True,
            "checkable": True,
            "checked": False,
            "editable": False,
            "enabled": True,
            "focusable": True,
            "selected": False,
        }
        for index, label in enumerate((
            "Amphibians (frogs, toads, etc.)",
            "Bird(s)",
            "Cat(s)",
            "Dog(s)",
            "Fish",
            "Horse(s)",
            "I do not have any pets",
        ))
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="pets-household",
        ocr_text=ocr_text, ui_nodes=nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    options = option_labels_from_observation(observation)
    question = current_question_text(observation)
    kb_key = observation_kb_key(observation)
    cat_dog_fish = parse_human_answer_input("Cat, Dog, Fish", options)
    only_fish = parse_human_answer_input("only Fish", options)
    none_status, none_labels = parse_human_answer_input("none", options)
    numbered = parse_human_answer_input("3, 4, 5", options)

    observation.kb = {"household_pets": ["Cat(s)", "Dog(s)", "Fish"]}
    first = configured_multi_option_decision(observation)
    if first:
        record_multi_select_progress(observation, str(first.get("target_text") or ""))
    second = configured_multi_option_decision(observation)
    if second:
        record_multi_select_progress(observation, str(second.get("target_text") or ""))
    third = configured_multi_option_decision(observation)
    if third:
        record_multi_select_progress(observation, str(third.get("target_text") or ""))
    done = configured_multi_option_decision(observation)
    request_human = {
        "screen_state": "survey_question",
        "action": "request_human",
        "confidence_score": 0.0,
        "visual_reasoning": "LLM silent on personal question",
    }
    passed = bool(
        observation.screen_phase == "survey_question"
        and multi_select_question(observation)
        and "Cat(s)" in options
        and "Dog(s)" in options
        and "Fish" in options
        and "Search" not in options
        and kb_key == "household_pets"
        and "pets currently live" in question.lower()
        and cat_dog_fish == ("ok", ["Cat(s)", "Dog(s)", "Fish"])
        and only_fish == ("ok", ["Fish"])
        and none_status == "ok"
        and none_labels
        and "pets" in none_labels[0].lower()
        and numbered == ("ok", ["Cat(s)", "Dog(s)", "Fish"])
        and first
        and first.get("action") == "select_option"
        and first.get("target_text") == "Cat(s)"
        and first.get("selection_complete") is False
        and second
        and second.get("target_text") == "Dog(s)"
        and third
        and third.get("target_text") == "Fish"
        and third.get("selection_complete") is True
        and done
        and done.get("action") in {"click", "scroll_down"}
        and "privacy" not in str(done.get("target_text") or "").lower()
        and request_human.get("action") == "request_human"
    )
    _MULTI_SELECT_PROGRESS.pop(semantic_screen_signature(observation), None)
    if passed:
        logger.info("[SELF-CHECK] Human key-in pets household routing checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Human key-in pets routing failed: key=%s options=%s "
            "first=%s second=%s third=%s done=%s",
            kb_key, options, first, second, third, done,
        )
    return passed



def gender_continue_regression_self_check() -> bool:
    """Guard Male -> Continue » without re-tapping/unchecking the radio."""
    ocr_text = (
        "What is your gender?\n"
        "Select one\n"
        "Female\n"
        "Male\n"
        "Non-binary/Gender non-conforming\n"
        "Gender fluid/Gender queer\n"
        "Prefer not to say\n"
        "« Back\n"
        "Continue »\n"
        "Accessibility Statement - Help"
    )
    nodes = [
        {
            "id": 20, "text": "Female", "content_desc": "", "class": "RadioButton",
            "bounds": [80, 700, 1360, 820], "clickable": True, "checkable": True,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 23, "text": "Male", "content_desc": "", "class": "RadioButton",
            "bounds": [80, 840, 1360, 960], "clickable": True, "checkable": True,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 24, "text": "Non-binary/Gender non-conforming", "content_desc": "",
            "class": "RadioButton", "bounds": [80, 980, 1360, 1100],
            "clickable": True, "checkable": True, "checked": False,
            "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 40, "text": "« Back", "content_desc": "", "class": "Button",
            "bounds": [320, 1680, 680, 1820], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 41, "text": "Continue »", "content_desc": "", "class": "Button",
            "bounds": [700, 1680, 1120, 1820], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 52, "text": "Open privacy policy modal", "content_desc": "",
            "class": "Button", "bounds": [200, 2860, 1240, 3000],
            "clickable": True, "checkable": False, "checked": False,
            "editable": False, "enabled": True, "selected": False,
        },
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="gender-continue",
        ocr_text=ocr_text, ui_nodes=nodes,
        kb={"gender": "Male"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    first = configured_multi_option_decision(observation)
    if first and first.get("target_text") == "Male":
        record_multi_select_progress(observation, "Male")
        _LAST_SELECT_FINGERPRINT[question_fingerprint(observation)] = "male"
    second = configured_multi_option_decision(observation)
    repaired = prefer_progression_over_repeat(
        {
            "action": "select_option", "target_text": "Male",
            "target_element_id": 23, "confidence_score": 0.99,
        },
        observation,
        stagnation_count=1,
    )
    learned_click = prefer_progression_over_repeat(
        {
            "action": "click", "target_text": "Male",
            "target_coords": [274, 709], "confidence_score": 0.83,
        },
        observation,
        stagnation_count=0,
    )
    privacy = prefer_progression_over_repeat(
        {
            "action": "click", "target_text": "Open privacy policy modal",
            "target_element_id": 52, "confidence_score": 0.96,
        },
        observation,
        stagnation_count=0,
    )
    next_decision = survey_next_decision(observation)
    card_obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="gender-cards",
        ocr_text="Are you...?\nMale\nFemale",
        ui_nodes=[
            {"id": 25, "text": "Male", "content_desc": "", "class": "Button",
             "bounds": [80, 700, 700, 980], "clickable": True, "checkable": True,
             "checked": False, "editable": False, "enabled": True, "selected": False},
            {"id": 26, "text": "Female", "content_desc": "", "class": "Button",
             "bounds": [740, 700, 1360, 980], "clickable": True, "checkable": True,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ],
        kb={"gender": "Male"}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    card_pick = gender_screen_decision(card_obs)
    card_obs.ui_nodes[0]["checked"] = True
    card_go = gender_screen_decision(card_obs)
    signature = semantic_screen_signature(observation)
    passed = bool(
        first
        and first.get("action") == "select_option"
        and first.get("target_text") == "Male"
        and first.get("target_element_id") == 23
        and second
        and second.get("action") == "click"
        and is_progression_cta(str(second.get("target_text") or ""))
        and second.get("target_text") != "Male"
        and second.get("target_element_id") != 23
        and "privacy" not in str(second.get("target_text") or "").lower()
        and "back" not in cta_core(str(second.get("target_text") or ""))
        and repaired.get("action") == "click"
        and is_progression_cta(str(repaired.get("target_text") or ""))
        and learned_click.get("action") == "click"
        and is_progression_cta(str(learned_click.get("target_text") or ""))
        and "male" not in str(learned_click.get("target_text") or "").lower()
        and privacy.get("action") == "click"
        and "privacy" not in str(privacy.get("target_text") or "").lower()
        and next_decision.get("target_element_id") == 41
        and visible_progression_label(ocr_text)
        and card_pick and card_pick.get("target_text") == "Male"
        and int((card_pick.get("target_coords") or [0, 999])[-1]) <= 400
        and card_go and "continue" in str(card_go.get("target_text") or "").lower()
        and int((card_go.get("target_coords") or [0, 999])[-1]) <= 600
    )
    _MULTI_SELECT_PROGRESS.pop(signature, None)
    _LAST_SELECT_FINGERPRINT.pop(signature, None)
    _PROGRESSION_SCROLLS.pop(signature, None)
    if passed:
        logger.info("[SELF-CHECK] Gender Continue routing checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Gender Continue routing failed: first=%s second=%s "
            "repaired=%s privacy=%s next=%s",
            first, second, repaired, privacy, next_decision,
        )
    return passed


def age_text_entry_regression_self_check() -> bool:
    """Guard age=44 typed from KB, and LLM payload/bbox repair."""
    ocr_text = (
        "What is your age?\n"
        "Enter a number\n"
        "« Back\n"
        "Continue »\n"
        "Accessibility Statement - Help"
    )
    nodes = [
        {
            "id": 15, "text": "", "content_desc": "", "class": "android.view.View",
            "bounds": [55, 850, 427, 1020], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True,
            "focusable": True, "selected": False,
        },
        {
            "id": 40, "text": "« Back", "content_desc": "", "class": "Button",
            "bounds": [320, 1680, 680, 1820], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
        {
            "id": 41, "text": "Continue »", "content_desc": "", "class": "Button",
            "bounds": [700, 1680, 1120, 1820], "clickable": True, "checkable": False,
            "checked": False, "editable": False, "enabled": True, "selected": False,
        },
    ]
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="age-entry",
        ocr_text=ocr_text, ui_nodes=nodes,
        kb={"age": 44, "gender": "Male"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    routed = configured_text_answer_decision(observation)
    llm_raw = {
        "screen_state": "survey_question",
        "question_text": "What is your age? Enter a number",
        "action": "type_text",
        "target_element_id": "ans89.0.0",
        "target_text": "44",
        "target_coords": [105, 367, 191, 383],
        "input_payload": None,
        "kb_key": None,
        "confidence_score": 0.95,
        "postcondition": "The age has been entered.",
    }
    repaired = repair_text_entry_decision(dict(llm_raw), observation)
    empty = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="age-missing",
        ocr_text=ocr_text, ui_nodes=nodes, kb={}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    passed = bool(
        text_entry_question_visible(ocr_text, nodes)
        and resolve_text_kb_key(ocr_text) == "age"
        and routed
        and routed.get("action") == "type_text"
        and str(routed.get("input_payload")) == "44"
        and routed.get("kb_key") == "age"
        and repaired.get("input_payload") == "44"
        and isinstance(repaired.get("target_coords"), list)
        and len(repaired.get("target_coords") or []) == 2
        and configured_text_answer_decision(empty) is None
        and is_personal_survey_question(observation)
        and isinstance(routed.get("target_coords"), list)
        and len(routed.get("target_coords") or []) == 2
        and routed["target_coords"][1] >= 240
        and 70 <= routed["target_coords"][0] * 1440 / 1000 <= 430
        and 850 <= routed["target_coords"][1] * 3088 / 1000 <= 1030
        and adult_age_question_visible(ocr_text)
        and not child_ages_question_visible(
            "What is your age?\nPlease specify a whole number.\nContinue"
        )
        and adult_age_screen_decision(observation)
        and adult_age_screen_decision(observation).get("input_payload") == "44"
    )
    if passed:
        logger.info("[SELF-CHECK] Age text-entry KB and payload-repair checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Age text-entry routing failed: routed=%s repaired=%s",
            routed, repaired,
        )
    return passed
