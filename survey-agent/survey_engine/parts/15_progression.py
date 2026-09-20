# 15_progression.py — shared engine namespace (do not import directly)



def salvage_option_from_decision(
    obs: Observation, decision: dict[str, Any]
) -> Optional[dict[str, Any]]:
    blob = " ".join(
        str(decision.get(key) or "")
        for key in ("target_text", "answer_reason", "postcondition", "visual_reasoning")
    ).lower()
    options = option_labels_from_observation(obs)
    pick = None
    for option in options:
        lowered = option.lower()
        if any(term in lowered and term in blob for term in (
            "very open", "somewhat open", "not at all open",
            "very likely", "strongly agree", "employed full",
        )):
            pick = option
            break
        if option.lower() in blob and len(option) > 12:
            pick = option
            break
    if pick is None:
        return inferred_preference_decision(obs)
    node = text_match_node(obs.ui_nodes, pick)
    return {
        **decision,
        "action": "select_option",
        "target_element_id": node.get("id") if node else None,
        "target_text": pick,
        "target_coords": None,
        "input_payload": pick,
        "confidence_score": 0.84,
        "postcondition": f"selected option is {pick}",
        "selection_complete": True,
    }


def survey_next_decision(obs: Observation) -> dict[str, Any]:
    """Ground Continue/Next. Never use Privacy Policy, Help, Back or Close."""
    if gender_choice_screen(obs):
        fill = gender_screen_decision(obs)
        if fill and "continue" in str(fill.get("target_text") or "").lower():
            return fill
        coords = gender_continue_milli(obs) or [500, 455]
        if int(coords[1]) >= 650:
            coords = [500, 455]
        logger.info("[WH] Gender answer done; Continue at %s", coords)
        return {
            "screen_state": "survey_question", "action": "click", "target_text": "Continue",
            "target_coords": coords, "coordinate_authoritative": True, "target_element_id": None,
            "confidence_score": 0.96, "postcondition": "screen changed",
            "answer_reason": "Male/Female is chosen; tap the orange Continue bar.",
        }
    if county_question_visible(obs.ocr_text) and not county_selection_complete(obs):
        fill = county_dropdown_decision(obs)
        if fill and not is_progression_cta(str(fill.get("target_text") or "")):
            logger.warning("[QUESTION ROUTER] Refusing Continue; county dropdown still needs %s.",
                           intended_county(obs))
            return fill
    if likert_slider_question_visible(obs.ocr_text) and not likert_complete(obs):
        logger.warning("[QUESTION ROUTER] Refusing Continue; Likert still missing %s.", likert_missing_names(obs))
        fill = likert_slider_decision(obs)
        if fill and "continue" not in str(fill.get("target_text") or "").lower():
            return fill
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Continue blocked: a like/dislike scale still has the up-arrow handle.",
            "action": "wait",
            "confidence_score": 0.7,
            "postcondition": "screen stable for re-observation",
        }
    if ranking_question_visible(obs.ocr_text) and not ranking_complete(obs):
        fill = ranking_decision(obs)
        if fill and "continue" not in str(fill.get("target_text") or "").lower():
            return fill
    if open_text_needs_more_words(obs) and not _OPEN_TEXT_TYPED.get(question_fingerprint(obs)):
        fill = open_text_answer_decision(obs)
        if fill:
            logger.warning("[QUESTION ROUTER] Refusing Continue; open text still needs more words.")
            return fill
    if captcha_code_question_visible(obs.ocr_text) and not captcha_field_complete(obs):
        fill = captcha_code_decision(obs)
        if fill and str(fill.get("action") or "") != "click":
            logger.warning("[QUESTION ROUTER] Refusing Next; captcha code is not in the box.")
            return fill
    if drag_drop_question_visible(obs.ocr_text) and not _DRAG_DONE.get("done"):
        fill = drag_drop_decision(obs)
        if fill and str(fill.get("action") or "") == "drag":
            logger.warning("[QUESTION ROUTER] Refusing Next; drag the tile into the box first.")
            return fill
    if children_count_question_visible(obs.ocr_text):
        fill = dependent_children_decision(obs)
        if fill:
            logger.warning("[QUESTION ROUTER] Children router action=%s target=%r",
                           fill.get("action"), fill.get("target_text"))
            return fill
    if child_ages_question_visible(obs.ocr_text):
        fill = child_age_text_decision(obs)
        if fill:
            logger.warning("[QUESTION ROUTER] Child-age router action=%s payload=%r",
                           fill.get("action"), fill.get("input_payload"))
            return fill
    if carousel_row_question_visible(obs.ocr_text):
        fill = carousel_row_decision(obs)
        if fill:
            logger.warning("[QUESTION ROUTER] Carousel needs %s %r, not Continue.",
                           fill.get("action"), fill.get("target_text"))
            return fill
    if maxdiff_question_visible(obs.ocr_text):
        fill = maxdiff_decision(obs)
        if fill and not fill.get("maxdiff_done"):
            logger.warning("[QUESTION ROUTER] MaxDiff needs %s %r, not Continue.",
                           fill.get("action"), fill.get("target_text"))
            return fill
    if select_all_apply_visible(obs.ocr_text):
        fill = select_all_apply_decision(obs)
        if fill and not fill.get("select_all_done"):
            logger.warning("[QUESTION ROUTER] Select-all needs %s %r, not Continue.",
                           fill.get("action"), fill.get("target_text"))
            return fill
    if survey_validation_error(obs) and not (
        children_count_question_visible(obs.ocr_text) and children_pick_complete(obs)
    ) and not (
        open_text_question_visible(obs.ocr_text)
        and (
            open_text_box_has_answer(obs)
            or _OPEN_TEXT_TYPED.get(open_text_screen_key(obs))
            or _OPEN_TEXT_DONE.get(open_text_screen_key(obs))
        )
    ):
        fill = exact_kb_option_decision(obs) or inferred_preference_decision(obs) or (
            dependent_children_decision(obs) if children_count_question_visible(obs.ocr_text) else None
        )
        if fill and not is_progression_cta(str(fill.get("target_text") or "")):
            logger.warning("[QUESTION ROUTER] Refusing Continue; validation error still needs a real option.")
            return fill
    if required_answer_missing(obs) and not question_select_issued(obs) and not teal_radio_filled(obs):
        inferred = inferred_preference_decision(obs) or single_choice_radio_decision(obs)
        if inferred:
            logger.warning("[QUESTION ROUTER] Refusing Continue; filling the unanswered choice first.")
            return inferred
        logger.warning("[QUESTION ROUTER] Refusing Continue; required answer is still missing.")
        human = capture_human_answer_decision(obs, "Required select-one is empty.")
        if human:
            return human
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "A required Select-one answer is still empty.",
            "action": "wait",
            "target_element_id": None, "target_text": None, "target_coords": None,
            "input_payload": None, "kb_key": None, "kb_write": False,
            "missing_fact_key": None, "confidence_score": 0.7,
            "postcondition": "screen stable for re-observation",
            "visual_reasoning": "Continue is visible but no radio is selected.",
        }
    labeled: list[dict[str, Any]] = []
    geometric: list[dict[str, Any]] = []
    for node in obs.ui_nodes:
        if not node.get("enabled") or not node.get("clickable"):
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            continue
        x1, y1, x2, y2 = [int(value) for value in bounds]
        if x2 <= x1 or y2 <= y1:
            continue
        text_label = node_text(node).strip()
        if text_label and is_forbidden_progression_target(text_label):
            continue
        if text_label and is_progression_cta(text_label):
            labeled.append(node)
            continue
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        width = x2 - x1
        height = y2 - y1
        if (
            obs.image_width * 0.20 <= center_x <= obs.image_width * 0.90
            and obs.image_height * 0.38 <= center_y <= obs.image_height * 0.92
            and width <= obs.image_width * 0.96
            and height <= obs.image_height * 0.18
            and width >= obs.image_width * 0.10
        ):
            geometric.append(node)

    target: Optional[dict[str, Any]] = None
    if labeled:
        target = min(
            labeled,
            key=lambda node: (
                0 if "continue" in cta_core(node_text(node)) else 1,
                abs(node_center(node)[1] / max(1, obs.image_height) - 0.62),
            ),
        )

    target_text = node_text(target) if target else None
    if not target_text or not is_progression_cta(target_text):
        ocr_label = visible_progression_label(obs.ocr_text)
        if ocr_label:
            target_text = ocr_label

    if not target and not target_text and geometric:
        option_labels = {label.lower() for label in option_labels_from_observation(obs)}
        geometric = [
            node for node in geometric
            if (not node_text(node).strip() or node_text(node).strip().lower() not in option_labels)
            and (not node_text(node).strip() or not is_forbidden_progression_target(node_text(node)))
        ]
        if geometric:
            target = min(
                geometric,
                key=lambda node: (
                    0 if node_center(node)[1] >= obs.image_height * 0.72 else 1,
                    abs(node_center(node)[0] / max(1, obs.image_width) - 0.55),
                    abs(node_center(node)[1] / max(1, obs.image_height) - 0.85),
                ),
            )

    if not target and not target_text:
        if soft_keyboard_visible(obs):
            pill = green_continue_pill_coords(obs, 0.36, 0.62) or visual_progression_coords(obs)
            if pill and int(pill[1]) < 700:
                logger.info("[QUESTION ROUTER] Keyboard up; Continue pill at %s", pill)
                return {
                    "screen_state": "survey_question",
                    "question_text": current_question_text(obs),
                    "answer_reason": "Text is entered; tap Continue above the keyboard.",
                    "action": "click",
                    "target_element_id": None,
                    "target_text": "Continue »",
                    "target_coords": pill,
                    "coordinate_authoritative": True,
                    "confidence_score": 0.95,
                    "postcondition": "screen changed",
                }
            return {
                "screen_state": "survey_question",
                "question_text": obs.ocr_text,
                "answer_reason": "No Next/Continue label yet; dismiss the keyboard so the bar is tappable.",
                "action": "back",
                "target_element_id": None,
                "target_text": "Soft keyboard",
                "target_coords": None,
                "input_payload": None,
                "kb_key": None,
                "kb_write": False,
                "missing_fact_key": None,
                "confidence_score": 0.9,
                "postcondition": "soft keyboard dismissed",
                "visual_reasoning": "Keyboard is up and Next was not parsed; BACK dismisses IME without leaving the question.",
            }
        signature = semantic_screen_signature(obs)
        scrolls = _PROGRESSION_SCROLLS.get(signature, 0)
        if scrolls < 2:
            _PROGRESSION_SCROLLS[signature] = scrolls + 1
            logger.info(
                "[QUESTION ROUTER] Continue/Next not visible; scrolling to reveal it (%s/2).",
                scrolls + 1,
            )
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": "The answer is complete but Continue/Next is not visible; scroll to reveal it.",
                "action": "scroll_down",
                "target_element_id": None,
                "target_text": None,
                "target_coords": None,
                "input_payload": None,
                "kb_key": None,
                "kb_write": False,
                "missing_fact_key": None,
                "confidence_score": 0.90,
                "postcondition": "screen changed",
                "visual_reasoning": "Progression CTA was not grounded; a bounded scroll is safer than tapping Privacy Policy.",
                "answer_provenance": "verified",
                "source_basis": "Current-screen OCR/UI progression search",
                "inference_confidence": 0.90,
            }

    fallback_coords = visual_progression_coords(obs)
    ocr = visible_continue_milli(obs)
    orange = orange_cta_milli(obs)
    if ocr:
        fallback_coords = ocr
    elif orange:
        fallback_coords = orange[-1]
    if target_text and obs.screenshot:
        ocr_center = ocr_text_center(Path(obs.screenshot), target_text)
        if ocr_center:
            fallback_coords = [
                int(max(0, min(1000, ocr_center[0] * 1000 / max(1, obs.image_width)))),
                int(max(0, min(1000, ocr_center[1] * 1000 / max(1, obs.image_height)))),
            ]
    pill = ocr or (orange[-1] if orange else None)
    if pill is None and obs.screenshot:
        pill = green_continue_pill_coords(obs, 0.38, 0.88) or fallback_coords
    if pill is None:
        pill = fallback_coords
    if open_text_question_visible(obs.ocr_text):
        _OPEN_TEXT_DONE[open_text_screen_key(obs)] = True
        logger.info("[OPEN TEXT] Screen marked done; next cycle must not retype.")
    logger.info(
        "[WH] Answer selected; tap Continue. node=%s text=%r coords=%s",
        target.get("id") if target else None, target_text, pill,
    )
    return {
        "screen_state": "survey_question",
        "question_text": obs.ocr_text,
        "answer_reason": "The current question already has a selected answer; advance once.",
        "action": "click",
        "target_element_id": target.get("id") if target else None,
        "target_text": target_text or None,
        "target_coords": pill if pill else (None if target else fallback_coords),
        "coordinate_authoritative": bool(pill),
        "input_payload": None,
        "kb_key": None,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.96 if target or target_text else 0.88,
        "postcondition": "screen changed",
        "visual_reasoning": (
            "A selected answer is visible and the Continue/Next control is grounded "
            "from current-screen labels, not the privacy footer."
        ),
        "answer_provenance": "verified",
        "source_basis": "Current accessibility state and selected-answer visual evidence",
        "inference_confidence": 0.96 if target or target_text else 0.88,
    }


def repair_decision_for_screen(
    decision: dict[str, Any], obs: Observation, stagnation_count: int = 0,
    quiet: bool = False, excluded_survey_labels: Optional[set[str]] = None,
) -> dict[str, Any]:
    """Enforce phase/action consistency and reject stale or hallucinated targets."""
    if obs.screen_phase == "permission_dialog":
        permission = permission_dialog_decision(obs)
        if permission:
            return permission

    if likert_slider_question_visible(obs.ocr_text) and not likert_complete(obs):
        target = str(decision.get("target_text") or "")
        if is_progression_cta(target) or "continue" in target.lower():
            fill = likert_slider_decision(obs)
            if fill and not is_progression_cta(str(fill.get("target_text") or "")):
                logger.warning("[DECISION REPAIR] Vetoed Continue; Likert still missing %s.", likert_missing_names(obs))
                return fill

    if obs.screen_phase == "document_picker":
        picker = document_picker_decision(obs)
        if picker:
            return picker

    if obs.screen_phase == "consent_overlay":
        consent = consent_overlay_decision(obs)
        if consent:
            if not quiet and decision.get("target_text") != consent.get("target_text"):
                logger.warning(
                    "[DECISION REPAIR] Replaced covered-screen action with cookie overlay action."
                )
            return consent

    dashboard_like, dashboard_reasons = dashboard_evidence(obs.ocr_text, obs.ui_nodes)
    if obs.screen_phase in {"dashboard", "navigation", "survey_question"} and dashboard_like:
        # Last safety barrier: even if an earlier OCR pass was ambiguous, never
        # execute an LLM answer against visible dashboard chrome. Rebuild tile
        # geometry from the current screenshot and route deterministically.
        dashboard_nodes = list(obs.ui_nodes)
        dashboard_tiles = list(obs.survey_tiles)
        if not dashboard_tiles and obs.screenshot and Path(obs.screenshot).exists():
            dashboard_nodes.extend(ocr_line_nodes(Path(obs.screenshot), psm=11))
            dashboard_tiles = extract_survey_tiles(
                dashboard_nodes, obs.image_width, obs.image_height
            )
        dashboard_obs = Observation(
            step=obs.step,
            screenshot=obs.screenshot,
            image_width=obs.image_width,
            image_height=obs.image_height,
            device_width=obs.device_width,
            device_height=obs.device_height,
            screen_hash=obs.screen_hash,
            ocr_text=obs.ocr_text,
            ui_nodes=dashboard_nodes,
            kb={},
            persona={},
            screen_phase="dashboard",
            survey_tiles=dashboard_tiles,
        )
        dashboard = choose_survey_tile_decision(
            dashboard_obs, stagnation_count, excluded_labels=excluded_survey_labels
        )
        if dashboard:
            if not quiet and (
                obs.screen_phase != "dashboard"
                or decision.get("question_text")
                or decision.get("kb_key")
                or dashboard_chrome_target(str(decision.get("target_text") or ""))
            ):
                logger.warning(
                    "[DECISION REPAIR] Replaced dashboard-chrome action with survey-card "
                    "routing; evidence=%s.", dashboard_reasons,
                )
            return dashboard
        if dashboard_chrome_target(str(decision.get("target_text") or "")):
            if not quiet:
                logger.warning(
                    "[DECISION REPAIR] Vetoed dashboard-chrome target=%r; no survey card "
                    "was grounded yet.", decision.get("target_text"),
                )
            return {
                **decision,
                "action": "wait",
                "target_element_id": None,
                "target_text": None,
                "target_coords": None,
                "confidence_score": 0.95,
                "postcondition": "screen stable for dashboard re-observation",
            }

    if obs.screen_phase == "survey_landing":
        navigation = navigation_cta_decision(obs)
        if navigation:
            return navigation

    action = str(decision.get("action") or "").lower()
    target_text = str(decision.get("target_text") or "").strip()
    coords = decision.get("target_coords")
    gesture_start = decision.get("gesture_start")
    gesture_end = decision.get("gesture_end")
    node = node_by_id(obs.ui_nodes, decision.get("target_element_id"))

    node_is_slider = bool(
        node and any(term in str(node.get("class") or "").lower() for term in ("seekbar", "slider"))
    )
    if (
        node and target_text
        and action != "select_matrix_cell"
        and not (action == "set_slider" and node_is_slider)
    ):
        actual = node_text(node).lower()
        wanted = target_text.lower()
        if not actual:
            matched = text_match_node(obs.ui_nodes, target_text)
            if matched and matched.get("id") != node.get("id"):
                if not quiet:
                    logger.warning(
                        "[DECISION REPAIR] Re-grounded blank node id=%s to text node id=%s for %r",
                        node.get("id"), matched.get("id"), target_text,
                    )
                decision["target_element_id"] = matched.get("id")
                node = matched
            else:
                if not quiet:
                    logger.warning(
                        "[DECISION REPAIR] Removed blank node id=%s for visible target=%r",
                        node.get("id"), target_text,
                    )
                decision["target_element_id"] = None
                node = None
        elif wanted not in actual and actual not in wanted:
            if not quiet:
                logger.warning(
                    "[DECISION REPAIR] Removed mismatched node id=%s text=%r for target=%r",
                    node.get("id"), actual, wanted
                )
            decision["target_element_id"] = None
            node = None

    if action in {
        "click", "select_option", "toggle_checkbox", "select_dropdown",
        "open_dropdown", "select_matrix_cell", "open_date_picker",
        "open_time_picker", "set_picker_value", "pick_file",
        "handle_permission", "long_press", "set_slider",
    }:
        if action != "select_matrix_cell" and not node and target_text:
            matched = text_match_node(obs.ui_nodes, target_text)
            if matched:
                decision["target_element_id"] = matched.get("id")
                node = matched
        text_visible = bool(target_text and target_text.lower() in obs.ocr_text.lower())
        grounded = bool(
            node
            or text_visible
            or (isinstance(coords, list) and len(coords) == 2)
        )
        if not grounded:
            salvaged = salvage_option_from_decision(obs, decision)
            if salvaged:
                if not quiet:
                    logger.warning(
                        "[DECISION REPAIR] Mapped ungrounded %s onto visible option %r.",
                        action, salvaged.get("target_text"),
                    )
                return salvaged
            if not quiet:
                logger.warning("[DECISION REPAIR] Replaced ungrounded %s action with wait.", action)
            return {
                **decision,
                "action": "wait",
                "confidence_score": 0.60,
                "postcondition": "screen stable for re-observation",
            }

    if child_ages_question_visible(obs.ocr_text):
        fill = child_age_text_decision(obs)
        if fill and str(fill.get("action") or "") != action:
            logger.warning("[DECISION REPAIR] Child-age screen; %s instead of %s.",
                           fill.get("action"), action)
            return fill

    if carousel_row_question_visible(obs.ocr_text):
        fill = carousel_row_decision(obs)
        if fill and (
            fill.get("action") == "select_option"
            or fill.get("carousel_advance")
        ) and (
            is_progression_cta(target_text)
            or action == "wait"
            or action != fill.get("action")
        ):
            logger.warning("[DECISION REPAIR] Carousel; %s %r instead of %s.",
                           fill.get("action"), fill.get("target_text"), action)
            return fill

    if drag_drop_question_visible(obs.ocr_text) and action != "drag":
        if not is_progression_cta(target_text) and not _DRAG_DONE.get("done"):
            if not quiet:
                logger.warning("[DECISION REPAIR] Rewriting %s into drag-and-drop.", action)
            return drag_drop_decision(obs)

    if action in {"swipe", "drag"}:
        valid_gesture = all(
            isinstance(point, list) and len(point) == 2
            for point in (gesture_start, gesture_end)
        )
        if not valid_gesture:
            if not quiet:
                logger.warning("[DECISION REPAIR] Replaced ungrounded %s action with wait.", action)
            return {
                **decision, "action": "wait", "confidence_score": 0.60,
                "postcondition": "screen stable for re-observation",
            }

    return decision
