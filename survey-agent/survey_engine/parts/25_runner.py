# 25_runner.py — shared engine namespace (do not import directly)
# ------------------------------------------------------------------------------
# Agent loop
# ------------------------------------------------------------------------------
def observe(
    step: int,
    save: bool = True,
    previous: Optional[Observation] = None,
    light: bool = False,
) -> Observation:
    if not light:
        ensure_survey_foreground()
    path, (iw, ih), sha, phash, saved = capture_screenshot(
        step,
        save=save,
        previous_hash=previous.screen_hash if previous and save else None,
        previous_path=previous.screenshot if previous and save else None,
    )
    if light and previous and previous.device_width:
        device_w, device_h = previous.device_width, previous.device_height
    else:
        device_w, device_h = get_device_size()
    text = ocr(path)
    if light and previous is not None:
        nodes = previous.ui_nodes
    else:
        nodes = dump_ui_nodes()
    phase = classify_screen_phase(text, nodes)
    if child_ages_question_visible(text) or children_count_question_visible(text) or carousel_row_question_visible(text):
        phase = "survey_question"
    if maxdiff_question_visible(text) or select_all_apply_visible(text) or quoted_select_instruction_visible(text):
        phase = "survey_question"
    if phase != "survey_question" and matrix_semantic_hint(text) and not looks_like_single_choice(text):
        phase = "survey_question"
    ocr_nodes: list[dict[str, Any]] = []
    maybe_dashboard = "featured survey" in (text or "").lower()
    if (not light) and phase in {"survey_question", "navigation"} and (
        phase != "survey_question" or maybe_dashboard
    ):
        # Sparse OCR if dashboard cards may have been misclassified.
        ocr_nodes = ocr_line_nodes(path, psm=11)
        recovered_phase = classify_screen_phase(text, nodes + ocr_nodes)
        if recovered_phase == "dashboard":
            _, reasons = dashboard_evidence(text, nodes + ocr_nodes)
            logger.warning(
                "[PHASE REPAIR] Reclassified %s as dashboard from redundant evidence=%s",
                phase, reasons,
            )
            phase = recovered_phase
    tiles: list[dict[str, Any]] = []
    if phase == "dashboard":
        _, reasons = dashboard_evidence(text, nodes + ocr_nodes)
        logger.info("[PHASE] Dashboard evidence=%s", reasons)
        if not ocr_nodes:
            # PSM 11 keeps two-column catalog cards separated.
            ocr_nodes = ocr_line_nodes(path, psm=11)
        tiles = extract_survey_tiles(nodes + ocr_nodes, iw, ih)
        if not tiles:
            dense_nodes = ocr_line_nodes(path, psm=6)
            tiles = extract_survey_tiles(nodes + dense_nodes, iw, ih)

    # Always attach the on-disk KB even if phase was briefly navigation.
    kb = load_kb()
    persona = load_persona() if phase == "survey_question" else {}

    logger.info(
        "[OBSERVE] step=%s phase=%s phash=%s OCR=%d chars UI=%d tiles=%d saved=%s",
        step, phase, phash, len(text), len(nodes), len(tiles), saved
    )
    observation = Observation(
        step=step,
        screenshot=str(path),
        image_width=iw,
        image_height=ih,
        device_width=device_w or iw,
        device_height=device_h or ih,
        screen_hash=phash,
        ocr_text=text,
        ui_nodes=nodes,
        kb=kb,
        persona=persona,
        screen_phase=phase,
        survey_tiles=tiles,
    )
    if not light and "build_screen_object_map" in globals():
        try:
            build_screen_object_map(observation, persist=SAVE_SCREEN_MAPS)
        except Exception as exc:
            logger.warning("[SCREEN MAP] Observation mapping failed without blocking the run: %s", exc)
    return observation
def main() -> int:
    if not initialize_fresh_run():
        return 1

    logger.info("Version %s change set: %s", VERSION, "; ".join(CHANGELOG[VERSION]))

    if not preflight():
        return 1

    state = {
        "version": VERSION,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "steps": 0,
        "completed": False,
        "last_screen_hash": None,
    }
    write_state(state)

    previous: Optional[Observation] = None
    last_saved: Optional[Observation] = None
    no_change_count = 0
    active_survey_label: Optional[str] = None
    failed_survey_labels: set[str] = set()
    pending_question_advance = False

    for step in range(1, MAX_AGENT_STEPS + 1):
        logger.info("-" * 78)
        logger.info("AGENT STEP %s/%s", step, MAX_AGENT_STEPS)

        obs = observe(step, previous=last_saved)
        last_saved = obs
        state["steps"] = step
        state["last_screen_hash"] = obs.screen_hash
        state["screen_phase"] = obs.screen_phase
        write_state(state)

        if obs.screen_phase != "survey_question":
            pending_question_advance = False

        if previous and obs.screen_hash == previous.screen_hash:
            no_change_count += 1
        else:
            no_change_count = 0
            if previous and question_fingerprint(obs) != question_fingerprint(previous):
                pending_question_advance = False

        if no_change_count:
            logger.warning(
                "[STAGNATION] phase=%s unchanged_cycles=%s/%s",
                obs.screen_phase, no_change_count, MAX_STAGNATION_CYCLES
            )
        decision: Optional[dict[str, Any]] = None
        decision_source = "router"
        consent_screen = i_agree_consent_visible(obs.ocr_text)
        if consent_screen:
            obs.screen_phase = "survey_question"
            decision = i_agree_consent_decision(obs)
            decision_source = "router-i-agree"
        elif gender_choice_screen(obs) and not gender_radio_list(obs):
            obs.screen_phase = "survey_question"
            decision = gender_screen_decision(obs)
            decision_source = "router-gender"
        elif quoted_select_instruction_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = quoted_instruction_decision(obs)
            decision_source = "router-quoted-select"
        elif smartphone_brand_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = smartphone_brand_decision(obs)
            decision_source = "router-phone"
        elif heard_of_assistants_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = heard_of_assistants_decision(obs)
            decision_source = "router-heard-of"
        elif birth_date_question_visible(obs.ocr_text) or adult_age_question_visible(obs.ocr_text):
            obs.screen_phase = "survey_question"
            decision = birth_date_decision(obs) if birth_date_question_visible(obs.ocr_text) else adult_age_screen_decision(obs)
            decision_source = "router-age"
        else:
            gated, halt = stagnation_gate(obs, no_change_count)
            if halt:
                state["completed"] = False
                state["stopped_reason"] = "bounded_stagnation_limit"
                write_state(state)
                logger.error(
                    "[STAGNATION STOP] Unchanged after %s cycles and VLM tries=%s.",
                    MAX_STAGNATION_CYCLES, _STAGNATION_VLM_TRIES,
                )
                return 2
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
                    obs, no_change_count, excluded_labels=failed_survey_labels
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
                    pending_question_advance
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
                        decision = configured_text_answer_decision(obs, stagnation_count=no_change_count)
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
            prompt = build_observation_prompt(obs, ultra_compact=False)
            compact_retry_prompt = build_observation_prompt(obs, ultra_compact=True)
            try:
                raw, backend = call_vlm(
                    prompt,
                    Path(obs.screenshot),
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
                        prompt, Path(obs.screenshot), compact_retry_prompt, prefer_flash=True
                    )
                    decision = parse_json_response(raw)
                    decision_source = backend
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
                        return 2
                else:
                    decision = local_fallback_decision(obs)
                    if decision:
                        decision_source = "router"
                        logger.info("[ROUTER] Recovered after LLM HTTP %s.", status)
                    else:
                        logger.warning("[LOCAL] No router after VLM HTTP failure; waiting.")
                        time.sleep(1.5)
                        previous = obs
                        continue
            except Exception as exc:
                logger.error("[LLM] failure: %s", exc)
                decision = local_fallback_decision(obs)
                if decision:
                    decision_source = "router"
                    logger.info("[ROUTER] Recovered after VLM failure.")
                else:
                    logger.warning("[LOCAL] No router and VLM unavailable; waiting.")
                    time.sleep(1.5)
                    previous = obs
                    continue

        if (
            decision
            and str(decision.get("action") or "").lower() in {"type_text", "type_comment"}
            and decision.get("input_payload") in (None, "")
        ):
            decision = repair_text_entry_decision(decision, obs)
        if (
            decision
            and is_personal_survey_question(obs)
            and str(decision.get("action") or "").lower() in {"type_text", "request_human"}
            and decision.get("input_payload") in (None, "")
        ):
            human_decision = capture_human_answer_decision(
                obs, "Model returned a personal answer without a typeable payload."
            )
            if human_decision:
                decision = human_decision
                decision_source = "human"
        decision = apply_authorized_personal_fallback(decision, obs)
        decision = repair_decision_for_screen(
            decision,
            obs,
            no_change_count,
            excluded_survey_labels=failed_survey_labels,
        )
        decision = authorize_grounded_terminal_close(decision, obs)
        decision = repair_text_entry_decision(decision, obs)
        consent_screen = i_agree_consent_visible(obs.ocr_text)
        if consent_screen:
            decision = i_agree_consent_decision(obs, decision)
        else:
            if decision and not str(decision.get("target_text") or "").strip():
                decision["target_text"] = "grounded-tap"
            decision = prefer_progression_over_repeat(decision, obs, no_change_count)
        decision = inspect_decision(obs, decision)
        if i_agree_consent_visible(obs.ocr_text):
            decision = i_agree_consent_decision(obs, decision)
        if decision.get("screen_state") == "dashboard":
            # A phase-repaired home action is deterministic routing, not a
            # learned survey answer. Never store it in learned_screen_actions.
            decision_source = "router"
        if decision.get("screen_state") == "dashboard" and decision.get("action") == "click":
            selected_label = str(decision.get("target_text") or "").strip()
            if selected_label.lower().startswith("featured survey"):
                active_survey_label = selected_label
        if decision.get("terminal_close") is True and active_survey_label:
            failed_survey_labels.add(active_survey_label)
            state["failed_survey_labels"] = sorted(failed_survey_labels)
            write_state(state)
            logger.info(
                "[SURVEY SKIP] Marked terminal survey unavailable for this run: %s",
                active_survey_label,
            )
        if (
            decision
            and not decision.get("input_payload")
            and is_progression_cta(str(decision.get("target_text") or ""))
            and (
                looks_like_single_choice(obs.ocr_text)
                or "please select an answer" in re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
            )
        ):
            fill = single_choice_radio_decision(obs)
            if fill and fill.get("input_payload"):
                logger.warning(
                    "[PAYLOAD] Continue had payload=None on a Select-one page; using %r instead.",
                    fill.get("input_payload"),
                )
                decision = fill
        confidence = float(decision.get("confidence_score", 0))
        logger.info("[LLM DECISION] %s", json.dumps(decision, ensure_ascii=False))

        # Never allow a low-confidence destructive/navigation action to continue.
        if confidence < LOW_CONFIDENCE and decision.get("action") not in {"wait", "scroll_down", "scroll_up", "request_human"}:
            if select_all_apply_visible(obs.ocr_text):
                alt = select_all_apply_decision(obs)
                if alt:
                    decision = alt
                    logger.info("[SELECT ALL] Replaced low-confidence VLM with local checklist.")
                else:
                    decision = {"action": "scroll_down", "confidence_score": 0.9, "postcondition": "screen changed"}
            elif maxdiff_question_visible(obs.ocr_text):
                alt = maxdiff_decision(obs)
                if alt:
                    decision = alt
                    logger.info("[MAXDIFF] Replaced low-confidence VLM action with local most/least taps.")
                else:
                    decision = {"action": "wait", "confidence_score": 0.9, "postcondition": "screen stable for re-observation"}
            elif matrix_grid_visible(obs):
                alt = configured_matrix_decision(obs)
                if alt:
                    decision = alt
                    logger.info("[MATRIX] Replaced low-confidence VLM action with local matrix fill.")
                else:
                    decision = {
                        "action": "scroll_down",
                        "confidence_score": 0.9,
                        "postcondition": "screen changed",
                        "visual_reasoning": "Low-confidence VLM on a matrix; scrolling instead of request_human.",
                    }
            elif drag_drop_question_visible(obs.ocr_text):
                alt = drag_drop_decision(obs)
                if alt:
                    decision = alt
                    logger.info("[DRAG] Replaced low-confidence VLM action with local drag-and-drop.")
            elif obs.screen_phase in {"survey_landing", "navigation"} or info_page_needs_scroll(obs):
                decision = scroll_until_cta_decision(obs) or {
                    "action": "scroll_down",
                    "confidence_score": 0.9,
                    "postcondition": "screen changed",
                    "visual_reasoning": "Low-confidence VLM on an info/landing page; scrolling for a CTA.",
                }
            else:
                decision = {
                    "action": "request_human",
                    "visual_reasoning": f"Confidence {confidence:.2f} is below safety threshold.",
                    "confidence_score": confidence,
                }

        if (
            str(decision.get("action") or "").lower() == "request_human"
            and obs.screen_phase == "survey_question"
        ):
            human_decision = capture_human_answer_decision(
                obs,
                str(decision.get("visual_reasoning") or "Model requested human help."),
            )
            if human_decision:
                decision = human_decision
                decision_source = "human"
                confidence = float(decision.get("confidence_score") or 0.99)
                logger.info("[HUMAN CATCH] Replaced request_human with keyed-in answer.")

        provenance = str(decision.get("answer_provenance") or "declared").lower()
        should_persist = provenance != "inferred" or PERSIST_INFERRED_ANSWERS
        if (
            should_persist
            and decision.get("kb_write") is True
            and decision.get("kb_key")
            and decision.get("input_payload") not in (None, "")
            and not is_chrome_option_label(str(decision.get("input_payload") or ""))
            and not re.match(r"^\d{1,2}_\d{2}_", str(decision.get("kb_key") or ""))
        ):
            # The model must explicitly opt into a KB write. Prefer doing this
            # only after a human-confirmed new fact; ordinary reuse of an existing
            # KB answer must never rewrite the KB.
            update_kb(
                str(decision["kb_key"]),
                decision["input_payload"],
                reason="Explicit answer-memory write requested by the decision policy.",
                provenance=provenance,
                confidence=float(decision.get("inference_confidence") or confidence),
                question=str(decision.get("question_text") or ""),
                source_basis=str(decision.get("source_basis") or decision.get("answer_reason") or ""),
            )

        result = execute_action(decision, obs)
        if result.success and decision.get("matrix_row_label"):
            label = str(decision.get("matrix_row_key") or decision.get("matrix_row_label"))
            progress = _MATRIX_SESSION.setdefault("done", [])
            if label and label not in progress:
                progress.append(label)
        if (
            _MATRIX_SESSION.get("active")
            and not matrix_grid_visible(obs)
            and not survey_validation_error(obs)
        ):
            reset_matrix_session()
        if (
            result.success
            and str(decision.get("action") or "").lower() in {"select_option", "toggle_checkbox", "click"}
            and decision.get("target_text")
            and not is_progression_cta(str(decision.get("target_text") or ""))
        ):
            if not (
                looks_like_single_choice(obs.ocr_text)
                and "please select an answer" in re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
            ):
                record_multi_select_progress(obs, str(decision.get("target_text")))
            label = str(decision.get("target_text") or "").strip().lower()
            _LAST_SELECT_FINGERPRINT[question_fingerprint(obs)] = label
            _LAST_SELECT_FINGERPRINT[semantic_screen_signature(obs)] = label
            rank_item = str(decision.get("rank_item") or decision.get("target_text") or "").strip()
            if ranking_question_visible(obs.ocr_text) and rank_item:
                done = _RANK_PROGRESS.setdefault(question_fingerprint(obs), [])
                if rank_item not in done:
                    done.append(rank_item)
            likert_item = str(decision.get("likert_item") or "").strip()
            coords = decision.get("target_coords") or []
            tap_ok = isinstance(coords, list) and len(coords) == 2 and int(coords[1]) >= 200
            if likert_slider_question_visible(obs.ocr_text) and likert_item and tap_ok:
                rated = _LIKERT_PROGRESS.setdefault(question_fingerprint(obs), [])
                if likert_item not in rated:
                    rated.append(likert_item)
        action_log_row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "step": step,
            "action": decision.get("action"),
            "target": decision.get("target_text") or decision.get("target_element_id") or decision.get("target_coords"),
            "payload": decision.get("input_payload"),
            "decision_source": decision_source,
            "confidence": confidence,
            "learned_action_confidence": decision.get("learned_action_confidence"),
            "screen_phase": obs.screen_phase,
            "post_action_phase": "",
            "postcondition": decision.get("postcondition"),
            "verified": "",
            "success": result.success,
            "changed": "",
            "message": result.message,
        }

        if not result.success:
            log_action({**action_log_row, "verified": False, "changed": False})
            logger.warning("[ACTION FAILED] %s", result.message)
            update_learned_screen_action(obs, decision, False, decision_source)
            update_rl_policy(obs, decision, False, after=None)
            if decision.get("action") == "request_human":
                human_decision = capture_human_answer_decision(
                    obs,
                    str(decision.get("visual_reasoning") or "Human intervention requested."),
                )
                if human_decision:
                    decision = human_decision
                    decision_source = "human"
                    confidence = float(decision.get("confidence_score") or 0.99)
                    logger.info("[HUMAN CATCH] Recovered after request_human execute failure.")
                    previous = obs
                    continue
                state["completed"] = False
                state["stopped_reason"] = "human_intervention_required"
                write_state(state)
                return 2
            previous = obs
            continue

        time.sleep(POST_ACTION_WAIT)

        # Verify the action. A successful ADB command is not the same thing as
        # a successful UI operation.
        if decision.get("action") in {"finish"}:
            log_action({**action_log_row, "verified": True, "changed": False})
            state["completed"] = True
            state["finished_at"] = datetime.now().isoformat(timespec="seconds")
            write_state(state)
            logger.info("Survey Execution Session Ended: FINISH reported by LLM.")
            return 0

        try:
            after = observe(step * 1000 + 1, save=False, previous=obs, light=True)
        except Exception as exc:
            log_action({
                **action_log_row,
                "message": f"{result.message} Verification unavailable: {exc}",
            })
            logger.warning("[VERIFY] Could not capture post-action state: %s", exc)
            previous = obs
            continue

        verified = verify_postcondition(decision, obs, after)
        log_action({
            **action_log_row,
            "post_action_phase": after.screen_phase,
            "verified": verified,
            "changed": obs.screen_hash != after.screen_hash,
        })
        logger.info("[VERIFY] postcondition=%r verified=%s", decision.get("postcondition"), verified)
        update_learned_screen_action(obs, decision, verified, decision_source, after=after)
        update_rl_policy(obs, decision, verified, after=after)
        if verified and decision.get("carousel_item") and not decision.get("carousel_advance"):
            _CAROUSEL_SESSION["tap_try"] = 0
        if not verified and decision.get("carousel_review"):
            _CAROUSEL_SESSION["review_done"] = True
            logger.warning("[CAROUSEL] Left review did not change the screen; Continue on the next cycle.")
        if decision.get("carousel_advance") and after:
            before_item = str(decision.get("carousel_item") or "")
            after_item = carousel_current_item(after)
            if before_item and after_item and before_item.lower() == after_item.lower():
                _CAROUSEL_SESSION["right_stagnant"] = int(_CAROUSEL_SESSION.get("right_stagnant") or 0) + 1
                logger.info("[CAROUSEL] Right arrow did not change item %r stagnant=%s",
                            after_item, _CAROUSEL_SESSION["right_stagnant"])
            else:
                _CAROUSEL_SESSION["right_stagnant"] = 0
        improve_survey_intelligence(
            obs, decision, verified=verified, source=decision_source,
            issue="" if verified else str(decision.get("postcondition") or decision.get("action") or ""),
        )
        if not verified and decision_source in {"gemini-lite", "llm", "salad"}:
            _VLM_STATE["prefer_flash"] = True
            logger.warning("[VLM] Postcondition failed on %s; next unknown screen uses Gemini Flash.", decision_source)
        try:
            if after.screenshot:
                Path(after.screenshot).unlink(missing_ok=True)
        except Exception:
            pass

        if not verified:
            record_failed_tap(obs, decision)
            recovery = recover_from_failure(obs, decision, 1)
            if recovery:
                logger.warning("[VERIFY] Postcondition failed; next loop re-observes or asks the image LLM.")
            previous = after
        else:
            action_name = str(decision.get("action") or "").lower()
            if action_name in {"select_option", "toggle_checkbox"} and decision.get("target_text"):
                record_multi_select_progress(obs, str(decision.get("target_text")))
            completed_complex_answer = bool(decision.get("selection_complete"))
            if action_name == "select_matrix_cell" and matrix_question(after):
                completed_complex_answer = matrix_question_complete(after)
            simple_select_complete = (
                action_name == "select_option"
                and not multi_select_question(obs)
                and not matrix_question(obs)
            )
            if obs.screen_phase == "survey_question" and (
                simple_select_complete
                or action_name in {"type_text", "type_comment", "set_slider"}
                or completed_complex_answer
            ):
                pending_question_advance = True
                logger.info(
                    "[QUESTION STATE] Answer entry verified; next cycle will ground progression."
                )
            elif pending_question_advance and action_name == "click":
                pending_question_advance = False
            no_change_count = 0
            previous = obs

    state["completed"] = False
    state["stopped_reason"] = "max_agent_steps_reached"
    write_state(state)
    logger.error("Maximum agent steps reached without explicit finish.")
    return 3
