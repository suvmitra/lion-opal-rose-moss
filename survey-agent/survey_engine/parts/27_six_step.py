# 27_six_step.py — one loop for every survey screen
# 1 map controls  2 one model question  3 knowledge-base or one terminal ask
# 4 tap the mapped coordinate  5 verify the answer  6 footer only after that


class _SkipVlm(Exception):
    """Local plan already exists, or there is no screenshot file."""


_SIX_STEP = {"signature": "", "verified": False}


def six_step_ask(obs: Optional[Observation] = None) -> str:
    return (
        "SIX STEPS. Reply with one JSON action only.\n"
        "1. Name the unanswered control: text box, radio, checkbox, dropdown, rank, or slider.\n"
        "2. Quote what is already filled and any red required banner.\n"
        "3. If this is a personal fact, use the KB/persona value. Do not invent a different one.\n"
        "4. target_coords are milli 0-1000 from the control map. Do not reuse a stale node id.\n"
        "5. Do not tap Continue, Next, Submit, or an arrow until that answer is visible.\n"
        "6. A hash change while the same question remains is not progress.\n"
        + (("SCREEN_CONTRACT=" + interaction_contract_prompt(obs) + "\n") if obs is not None else "")
    )


def _six_see(obs: Observation) -> dict:
    scene = {"controls": []}
    try:
        scene = build_screen_object_map(obs)
    except Exception as exc:
        logger.warning("[SIX] 1 map failed: %s", exc)
    controls = scene.get("controls") or []
    kinds: dict[str, int] = {}
    for item in controls:
        key = str(item.get("role") or item.get("kind") or "?")
        kinds[key] = kinds.get(key, 0) + 1
    signature = active_question_signature(obs)
    contract = interaction_contract_state(obs)
    logger.info(
        "[SIX] 1 MAP sig=%s controls=%s kinds=%s verified=%s",
        signature[:90], len(controls), kinds, contract.get("complete"),
    )
    return scene


def _six_ground(obs: Observation, decision: Optional[dict]) -> Optional[dict]:
    """Step 4: prefer the control map over a remembered node id."""
    if not isinstance(decision, dict):
        return decision
    decision["six_step"] = True
    if decision.get("skip_object_grounding"):
        return decision
    text = str(decision.get("target_text") or "").strip()
    role = "text_input" if str(decision.get("action") or "") == "type_text" else None
    if text and not is_progression_cta(text):
        found = find_screen_control(obs, text, role)
        milli = (found or {}).get("milli")
        if isinstance(milli, list) and len(milli) == 2:
            decision["target_coords"] = [int(milli[0]), int(milli[1])]
            decision["target_element_id"] = None
            decision["coordinate_authoritative"] = True
            logger.info("[SIX] 4 MAP %r milli=%s", text, decision["target_coords"])
    return decision


def _footer_tap(decision: dict) -> bool:
    if str(decision.get("action") or "").lower() != "click":
        return False
    text = str(decision.get("target_text") or "")
    folded = text.lower().strip()
    return bool(
        is_progression_cta(text)
        or folded in {"arrow", "next", "continue", "next question", "submit"}
        or folded.startswith("next question")
    )


def _six_lock_footer(obs: Observation, decision: Optional[dict]) -> Optional[dict]:
    """Step 6: Continue/Next/arrow only after the answer is on screen."""
    if not isinstance(decision, dict) or not _footer_tap(decision):
        return decision
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    banner = required_validation_visible(obs) or any(
        token in blob for token in (
            "this question is required", "please select an answer",
            "please provide an answer", "please fill in this field",
        )
    )
    if adult_age_question_visible(obs.ocr_text) and not adult_age_in_field(obs, str(adult_age_payload(obs))):
        logger.warning("[SIX] 6 age box is empty; type it before the footer")
        return adult_age_screen_decision(obs) or decision
    if gender_choice_screen(obs) and not selected_option_visual(obs, "Male"):
        logger.warning("[SIX] 6 Male is not checked; select it before the footer")
        return gender_screen_decision(obs) or decision
    answered = bool(
        answer_already_selected(obs) or teal_radio_filled(obs) or _SIX_STEP.get("verified")
    )
    if banner and not answered:
        logger.warning("[SIX] 6 required banner; scrolling instead of the footer")
        return {
            "screen_state": "survey_question",
            "action": "scroll_down",
            "target_text": None,
            "target_element_id": None,
            "target_coords": None,
            "input_payload": None,
            "confidence_score": 0.9,
            "postcondition": "screen changed",
            "six_step": True,
            "answer_reason": "Required banner is still visible. Scroll to the unanswered control.",
        }
    logger.info("[SIX] 6 FOOTER allowed %r", decision.get("target_text"))
    decision["six_step"] = True
    decision["six_step_footer"] = True
    return decision


def note_six_step_result(before: Observation, after: Observation, decision: dict, verified: bool) -> None:
    """Step 5: the same question after a footer tap is not progress."""
    before_sig = active_question_signature(before)
    after_sig = active_question_signature(after)
    if decision.get("six_step_footer") and before_sig == after_sig:
        _SIX_STEP["verified"] = False
        logger.warning("[SIX] 5 footer stayed on %s", before_sig[:80])
        return
    if before_sig != after_sig and verified:
        _SIX_STEP["signature"] = after_sig
        _SIX_STEP["verified"] = False
        logger.info("[SIX] 5 question changed")
        return
    action = str((decision or {}).get("action") or "").lower()
    if verified and action in {"type_text", "type_comment", "select_option", "toggle_checkbox", "set_slider"}:
        _SIX_STEP["signature"] = before_sig
        _SIX_STEP["verified"] = True
        logger.info("[SIX] 5 answer verified on %s", before_sig[:80])


def plan_six_steps(obs, stagnation, pending_advance, excluded_labels):
    """Every screen: map, one question, fact, mapped tap. Footer is last."""
    _six_see(obs)
    decision, source, halt = _classify_screen(obs, stagnation, pending_advance, excluded_labels)
    if halt:
        return decision, source, halt
    if isinstance(decision, dict) and decision.get("kb_key"):
        logger.info("[SIX] 3 FACT %s=%s", decision.get("kb_key"), decision.get("input_payload"))
    elif source == "human":
        logger.info("[SIX] 3 FACT missing; one terminal prompt")
    elif isinstance(decision, dict):
        logger.info("[SIX] 3 %s %s", decision.get("action"), decision.get("target_text"))
    decision = _six_ground(obs, decision)
    decision = _six_lock_footer(obs, decision)
    decision = enforce_interaction_contract(obs, decision)
    return decision, source, None


def _classify_screen(obs, stagnation, pending_advance, excluded_labels):
    decision = None
    decision_source = "router"
    consent_screen = i_agree_consent_visible(obs.ocr_text)
    if consent_screen:
        obs.screen_phase = "survey_question"
        decision = i_agree_consent_decision(obs)
        decision_source = "router-i-agree"
    elif gender_choice_screen(obs):
        obs.screen_phase = "survey_question"
        decision = gender_screen_decision(obs)
        decision_source = "router-gender"
    elif quoted_select_instruction_visible(obs.ocr_text):
        obs.screen_phase = "survey_question"
        decision = quoted_instruction_decision(obs)
        decision_source = "router-quoted-select"
    elif smartphone_brand_question_visible(obs.ocr_text):
        obs.screen_phase = "survey_question"; decision = smartphone_brand_decision(obs); decision_source = "router-phone"
    elif pending_advance:
        decision = post_answer_flow_decision(obs, True)
        if decision: decision_source = "router-verified-footer"
    elif comfort_question_header_visible(obs.ocr_text) or comfort_scale_visible(obs.ocr_text):
        obs.screen_phase = "survey_question"; decision = comfort_likert_decision(obs); decision_source = "router-comfort"
    elif heard_of_assistants_visible(obs.ocr_text) or select_up_to_n_visible(obs.ocr_text):
        obs.screen_phase = "survey_question"
        decision = heard_of_assistants_decision(obs) or select_up_to_n_decision(obs)
        decision_source = "router-multi"
    elif birth_date_question_visible(obs.ocr_text) or adult_age_question_visible(obs.ocr_text):
        obs.screen_phase = "survey_question"
        decision = birth_date_decision(obs) if birth_date_question_visible(obs.ocr_text) else adult_age_screen_decision(obs)
        decision_source = "router-age"
    else:
        gated, halt = stagnation_gate(obs, stagnation)
        if halt:
            logger.error(
                "[STAGNATION STOP] Unchanged after %s cycles and VLM tries=%s.",
                MAX_STAGNATION_CYCLES, _STAGNATION_VLM_TRIES,
            )
            return None, decision_source, "stop"
        if gated:
            decision = gated
            decision_source = str(gated.pop("_source", "vlm-stagnation"))
            logger.info("[STAGNATION GATE] source=%s action=%s coords=%s",
                        decision_source, decision.get("action"), decision.get("target_coords"))

    if decision is None:
        decision_source = "router"
        if close_survey_confirm_visible(obs):
            obs.screen_phase = "survey_question"
            decision = close_survey_confirm_decision(obs)
        elif likert_slider_question_visible(obs.ocr_text, obs.ui_nodes):
            obs.screen_phase = "survey_question"
            decision = likert_slider_decision(obs)
        elif ranking_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = ranking_decision(obs)
        elif drag_drop_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = drag_drop_decision(obs)
        elif captcha_code_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = captcha_code_decision(obs)
        elif select_all_apply_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = select_all_apply_decision(obs)
        elif i_agree_consent_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = i_agree_consent_decision(obs)
        elif looks_like_single_choice(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = single_choice_radio_decision(obs)
        elif open_text_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = open_text_answer_decision(obs)
        elif county_list_context(obs):
            obs.screen_phase = "survey_question"
            decision = county_dropdown_decision(obs)
        elif children_count_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = dependent_children_decision(obs)
        elif child_ages_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = child_age_text_decision(obs)
        elif carousel_row_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = carousel_row_decision(obs)
        elif maxdiff_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = maxdiff_decision(obs)
        elif occupation_group_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = occupation_group_decision(obs)
        elif matrix_grid_visible(obs):
            obs.screen_phase = "survey_question"
            if not obs.kb:
                obs.kb = load_kb()
            if not obs.persona:
                obs.persona = load_persona()
            decision = configured_matrix_decision(obs)
        elif obs.screen_phase == "dashboard":
            decision = choose_survey_tile_decision(
                obs, stagnation, excluded_labels=excluded_labels
            )
        elif obs.screen_phase == "permission_dialog":
            decision = permission_dialog_decision(obs)
        elif obs.screen_phase == "document_picker":
            decision = document_picker_decision(obs)
        elif obs.screen_phase == "consent_overlay":
            decision = consent_overlay_decision(obs)
        elif obs.screen_phase in {"survey_landing", "navigation"}:
            if drag_drop_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = drag_drop_decision(obs)
            elif captcha_code_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = captcha_code_decision(obs)
            elif likert_slider_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = likert_slider_decision(obs)
            elif ranking_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = ranking_decision(obs)
            elif child_ages_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = child_age_text_decision(obs)
            elif children_count_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = dependent_children_decision(obs)
            elif carousel_row_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = carousel_row_decision(obs)
            elif maxdiff_question_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = maxdiff_decision(obs)
            elif select_all_apply_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = select_all_apply_decision(obs)
            elif i_agree_consent_visible(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = i_agree_consent_decision(obs)
            elif looks_like_single_choice(obs.ocr_text):
                obs.screen_phase = "survey_question"
                decision = single_choice_radio_decision(obs)
            else:
                decision = (
                    navigation_cta_decision(obs)
                    or rl_policy_decision(obs)
                    or lesson_action_decision(obs)
                    or generalized_unseen_router(obs)
                )
        elif obs.screen_phase == "survey_question":
            if likert_slider_question_visible(obs.ocr_text):
                decision = likert_slider_decision(obs)
            if decision is None and ranking_question_visible(obs.ocr_text):
                decision = ranking_decision(obs)
            if decision is None and drag_drop_question_visible(obs.ocr_text):
                decision = drag_drop_decision(obs)
            if decision is None and captcha_code_question_visible(obs.ocr_text):
                decision = captcha_code_decision(obs)
            if decision is None and select_all_apply_visible(obs.ocr_text):
                decision = select_all_apply_decision(obs)
            if decision is None and looks_like_single_choice(obs.ocr_text):
                decision = single_choice_radio_decision(obs)
            if decision is None and open_text_question_visible(obs.ocr_text):
                decision = open_text_answer_decision(obs)
            if decision is None and county_question_visible(obs.ocr_text):
                decision = county_dropdown_decision(obs)
            if decision is None and children_count_question_visible(obs.ocr_text):
                decision = dependent_children_decision(obs)
            if decision is None and child_ages_question_visible(obs.ocr_text):
                decision = child_age_text_decision(obs)
            if decision is None and carousel_row_question_visible(obs.ocr_text):
                decision = carousel_row_decision(obs)
            if decision is None and maxdiff_question_visible(obs.ocr_text):
                decision = maxdiff_decision(obs)
            if decision is None:
                decision = lesson_action_decision(obs)
            if decision is None:
                replay = rl_policy_decision(obs)
                if replay:
                    decision = replay
            if decision is None:
                decision = generalized_unseen_router(obs)
            if decision is None and occupation_group_question_visible(obs.ocr_text):
                decision = occupation_group_decision(obs)
            if decision is None and matrix_question(obs):
                decision = configured_matrix_decision(obs)
            stored_multi = None if decision is not None else configured_multi_option_decision(obs)
            if decision is None and stored_multi is not None:
                decision = stored_multi
            if decision is None:
                decision = exact_kb_option_decision(obs)
            if decision is None:
                decision = configured_personal_answer_decision(obs)
            answered_this_question = bool(
                pending_advance
                or answer_already_selected(obs)
                or teal_radio_filled(obs)
                or question_select_issued(obs)
            )
            if decision is None and answered_this_question:
                decision = survey_next_decision(obs)
            elif decision is None and required_answer_missing(obs):
                decision = inferred_preference_decision(obs)
            else:
                if decision is not None:
                    pass
                # Exact, user-authorized mappings should not consume VLM context
                # or be lost to a transport/model limit. Unknown questions still
                # flow to the multimodal model below.
                if decision is None:
                    decision = configured_personal_answer_decision(obs)
                if decision is None:
                    decision = inferred_preference_decision(obs)
                if decision is None:
                    decision = configured_text_answer_decision(obs, stagnation_count=stagnation)
                if decision is None and is_personal_survey_question(obs):
                    kb_key = resolve_text_kb_key(obs.ocr_text) or observation_kb_key(obs)
                    if kb_or_persona_value(obs, kb_key) in (None, ""):
                        decision = capture_human_answer_decision(
                            obs, "Personal question has no knowledge-base value yet."
                        )
                        if decision is not None:
                            decision_source = "human"
                if decision is None:
                    decision = learned_action_decision(obs)
                    if decision is not None:
                        decision_source = "learned"
        elif obs.screen_phase == "loading":
            decision = {
                "screen_state": "loading", "question_text": "", "action": "wait",
                "target_element_id": None, "target_text": None, "target_coords": None,
                "input_payload": None, "kb_key": None, "kb_write": False,
                "missing_fact_key": None, "confidence_score": 0.95,
                "postcondition": "screen changed", "visual_reasoning": "Loading indicator visible.",
            }
        elif obs.screen_phase == "completion":
            decision = {
                "screen_state": "completion", "question_text": "", "action": "finish",
                "target_element_id": None, "target_text": None, "target_coords": None,
                "input_payload": None, "kb_key": None, "kb_write": False,
                "missing_fact_key": None, "confidence_score": 0.99,
                "postcondition": "survey completion screen visible",
                "visual_reasoning": "Completion text is visible.",
            }

    if decision is None:
        replay = rl_policy_decision(obs)
        if replay:
            decision = replay
            decision_source = "rl"
            logger.info("[RL] Policy supplied the action before VLM.")
    if decision is None:
        gen = generalized_unseen_router(obs)
        if gen:
            decision = gen
            decision_source = "generalized"
            logger.info("[GENERALIZE] Unseen-screen router supplied the action before VLM.")

    if decision is not None:
        logger.info("[ROUTER DECISION] %s", json.dumps(decision, ensure_ascii=False))
    else:
        shot = Path(str(obs.screenshot or ""))
        if not obs.screenshot or not shot.is_file():
            logger.info("[SIX] 2 no screenshot file; model is not called")
            decision = local_fallback_decision(obs)
            if decision:
                decision_source = "router"
        else:
            logger.info("[SIX] 2 ASK the model for one next action")
            prompt = six_step_ask(obs) + build_observation_prompt(obs, ultra_compact=False)
            compact_retry_prompt = six_step_ask(obs) + build_observation_prompt(obs, ultra_compact=True)
        try:
            if decision is not None or not obs.screenshot or not shot.is_file():
                raise _SkipVlm()
            raw, backend = call_vlm(
                prompt,
                shot,
                compact_retry_prompt,
                prefer_flash=bool(_VLM_STATE.get("prefer_flash")),
            )
            _VLM_STATE["prefer_flash"] = False
            logger.info("[LLM RAW] backend=%s %s", backend, raw[:2000])
            decision = parse_json_response(raw)
            decision_source = "llm" if backend == "salad" else backend
            confidence_now = float(decision.get("confidence_score") or 0)
            if (
                backend == "gemini-lite"
                and confidence_now < max(LOW_CONFIDENCE, 0.70)
                and gemini_configured()
            ):
                logger.warning("[VLM] Lite confidence %.2f; one Flash retry.", confidence_now)
                raw, backend = call_vlm(
                    prompt, shot, compact_retry_prompt, prefer_flash=True
                )
                decision = parse_json_response(raw)
                decision_source = backend
        except _SkipVlm:
            pass
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            logger.error("[LLM] HTTP failure: %s", exc)
            if status is not None and status >= 500:
                mark_salad_offline(f"HTTP {status}")
            if status is not None and 400 <= status < 500 and status != 429 and not gemini_configured():
                human_decision = capture_human_answer_decision(
                    obs, f"LLM HTTP {status} on a personal question"
                )
                if human_decision:
                    decision = human_decision
                    decision_source = "human"
                else:
                    logger.error(
                        "[LLM] Deterministic client error (%s); halting instead of repeating.",
                        status,
                    )
                    return None, decision_source, "stop"
            else:
                decision = local_fallback_decision(obs)
                if decision:
                    decision_source = "router"
                    logger.info("[ROUTER] Recovered after LLM HTTP %s.", status)
                else:
                    logger.warning("[LOCAL] No router after VLM HTTP failure; waiting.")
                    time.sleep(1.5)
                    return None, decision_source, "wait"
        except Exception as exc:
            logger.error("[LLM] failure: %s", exc)
            decision = local_fallback_decision(obs)
            if decision:
                decision_source = "router"
                logger.info("[ROUTER] Recovered after VLM failure.")
            else:
                logger.warning("[LOCAL] No router and VLM unavailable; waiting.")
                time.sleep(1.5)
                return None, decision_source, "wait"

    return decision, decision_source, None


def six_step_regression_self_check() -> bool:
    """Empty age types 44. Unchecked Male is selected. Neither page taps Next."""
    saved_age = dict(_AGE_SESSION)
    age = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="six-age",
        ocr_text="What age are you?\nEnter a number\nNext question",
        ui_nodes=[], kb={"age": 44, "gender": "Male"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _AGE_SESSION["typed"] = False
    age_plan, _, age_halt = plan_six_steps(age, 0, False, set())
    gender = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="six-gender",
        ocr_text="Are you...?\nMale\nFemale\nContinue",
        ui_nodes=[
            {"id": 11, "text": "Male", "content_desc": "", "class": "Button",
             "bounds": [80, 700, 700, 900], "clickable": True, "checkable": True,
             "checked": False, "editable": False, "enabled": True, "selected": False},
            {"id": 12, "text": "Female", "content_desc": "", "class": "Button",
             "bounds": [80, 940, 700, 1140], "clickable": True, "checkable": True,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ],
        kb={"gender": "Male"}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    gender_plan, _, gender_halt = plan_six_steps(gender, 0, False, set())
    checked = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="six-gender-next",
        ocr_text="What is your gender?\nMale\nFemale\nNext question",
        ui_nodes=[
            {"id": 27, "text": "Male", "content_desc": "", "class": "Button",
             "bounds": [234, 688, 1316, 832], "clickable": True, "checkable": True,
             "checked": True, "editable": False, "enabled": True, "selected": True},
            {"id": 39, "text": "Female", "content_desc": "", "class": "Button",
             "bounds": [234, 944, 1316, 1087], "clickable": True, "checkable": True,
             "checked": False, "editable": False, "enabled": True, "selected": False},
            {"id": 89, "text": "Next question", "content_desc": "", "class": "Button",
             "bounds": [777, 2708, 1358, 2831], "clickable": True, "checkable": False,
             "checked": False, "editable": False, "enabled": True, "selected": False},
        ],
        kb={"gender": "Male"}, persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    next_plan, _, next_halt = plan_six_steps(checked, 0, False, set())
    guarded = required_field_action_guard(checked, {
        "action": "click", "target_text": "Continue", "target_coords": [500, 455],
        "confidence_score": 0.97,
    })
    _AGE_SESSION.clear()
    _AGE_SESSION.update(saved_age)
    passed = bool(
        age_halt is None
        and age_plan
        and age_plan.get("action") == "type_text"
        and str(age_plan.get("input_payload")) == "44"
        and gender_halt is None
        and gender_plan
        and str(gender_plan.get("target_text") or "").lower() == "male"
        and not is_progression_cta(str(gender_plan.get("target_text") or ""))
        and next_halt is None
        and next_plan
        and next_plan.get("action") == "click"
        and "next" in str(next_plan.get("target_text") or "").lower()
        and int((next_plan.get("target_coords") or [0, 0])[1]) >= 800
        and guarded.get("action") == "click"
        and int((guarded.get("target_coords") or [0, 0])[1]) >= 800
    )
    if passed:
        logger.info("[SELF-CHECK] Six-step loop types 44, selects Male, then taps Next question.")
    else:
        logger.error(
            "[SELF-CHECK] Six-step loop failed age=%s gender=%s next=%s guarded=%s",
            age_plan, gender_plan, next_plan, guarded,
        )
    return passed
