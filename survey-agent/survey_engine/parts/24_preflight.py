# 24_preflight.py — shared engine namespace (do not import directly)



def terminal_modal_regression_self_check() -> bool:
    """Guard LLM close intent against the low-confidence safety rewrite."""
    nodes = [
        {
            "id": 3, "text": "", "content_desc": "Close Button",
            "resource_id": "topsurveys.paid.survey.money.cash:id/closeButton",
            "class": "android.widget.ImageButton", "bounds": [28, 107, 161, 240],
            "clickable": True, "checkable": False, "checked": False,
            "editable": False, "enabled": True, "focusable": True, "selected": False,
        }
    ]
    ocr_text = "We appreciate your interest, but unfortunately this survey is now closed."
    observation = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="terminal-modal",
        ocr_text=ocr_text, ui_nodes=nodes, kb={}, persona={},
        screen_phase=classify_screen_phase(ocr_text, nodes), survey_tiles=[],
    )
    llm_decision = {
        "screen_state": "closed_survey", "action": "click",
        "target_element_id": 3, "target_text": "Close Button",
        "target_coords": [28, 107, 161, 240], "confidence_score": 0.0,
        "postcondition": "Closed survey screen exited",
        "source_basis": "Close button clicked to exit survey",
    }
    repaired = repair_decision_for_screen(llm_decision, observation, quiet=True)
    authorized = authorize_grounded_terminal_close(repaired, observation)
    disqualified_text = (
        "You Didn't Qualify This Time. Unfortunately, you didn't qualify for this survey. Okay"
    )
    stale_nodes = [
        {
            "id": 20, "text": "Featured Surveys", "content_desc": "",
            "resource_id": "", "class": "android.widget.TextView",
            "bounds": [60, 900, 400, 960], "clickable": False,
            "checkable": False, "checked": False, "editable": False,
            "enabled": True, "focusable": False, "selected": False,
        }
    ]
    disqualified = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="disqualified-modal",
        ocr_text=disqualified_text, ui_nodes=stale_nodes, kb={}, persona={},
        screen_phase=classify_screen_phase(disqualified_text, stale_nodes), survey_tiles=[],
    )
    okay_exit = authorize_grounded_terminal_close(
        {"screen_state": "terminal_modal", "action": "wait", "confidence_score": 0.0},
        disqualified,
    )
    passed = bool(
        observation.screen_phase == "terminal_modal"
        and authorized.get("action") == "click"
        and authorized.get("target_element_id") == 3
        and float(authorized.get("confidence_score") or 0) >= LOW_CONFIDENCE
        and authorized.get("terminal_close") is True
        and disqualified.screen_phase == "terminal_modal"
        and okay_exit.get("action") == "click"
        and okay_exit.get("target_text") == "Okay"
        and okay_exit.get("target_coords") == [500, 900]
    )
    if passed:
        logger.info("[SELF-CHECK] Terminal-modal close routing checks passed.")
    else:
        logger.error(
            "[SELF-CHECK] Terminal-modal close routing failed: phase=%s decision=%s",
            observation.screen_phase, authorized,
        )
    return passed


def mark_salad_offline(reason: str) -> None:
    global _SALAD_ONLINE
    _SALAD_ONLINE = False
    logger.warning(
        "[SALAD] Offline (%s). Gemini stays in use; Salad will not be retried this run.",
        reason[:240],
    )


def prompt_operator_start_salad() -> None:
    """Gemini is unusable and Salad is down — ask the operator to start Salad."""
    if not sys.stdin.isatty():
        logger.error("[SALAD] Offline and Gemini failed; no TTY to ask the operator.")
        return
    print()
    print("Salad instance is not running and Gemini is not usable.")
    print("Start the Salad container, wait until it is healthy, then press Enter.")
    try:
        input("Press Enter after Salad is running> ")
    except EOFError:
        return
    global _SALAD_ONLINE
    _SALAD_ONLINE = True
    logger.info("[SALAD] Operator confirmed restart; Salad will be tried again.")


def local_fallback_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Used when Salad is 503/521/522 so the agent never stalls waiting on VLM."""
    for fn in (
        birth_date_decision,
        county_dropdown_decision,
        dependent_children_decision,
        child_age_text_decision,
        carousel_row_decision,
        lesson_action_decision,
        occupation_group_decision,
        ranking_decision,
        likert_slider_decision,
        captcha_code_decision,
        drag_drop_decision,
        open_text_answer_decision,
        exact_kb_option_decision,
        configured_personal_answer_decision,
        configured_multi_option_decision,
        inferred_preference_decision,
        configured_text_answer_decision,
        survey_next_decision,
    ):
        try:
            decision = fn(obs)
        except Exception as exc:
            logger.debug("[LOCAL FALLBACK] %s skipped: %s", fn.__name__, exc)
            decision = None
        if decision:
            logger.info("[LOCAL FALLBACK] %s -> %s %r",
                        fn.__name__, decision.get("action"), decision.get("target_text"))
            return decision
    return None


def preflight_s4_access() -> bool:
    """Verify the configured API key can access the configured S4 organization."""
    if not valid_salad_organization(SALAD_ORGANIZATION):
        logger.error(
            "[PREFLIGHT S4] Invalid or placeholder SALAD_ORGANIZATION=%r. "
            "Use the real lowercase organization slug from the Salad portal URL.",
            SALAD_ORGANIZATION,
        )
        return False

    url = f"{SALAD_STORAGE_URL}/organizations/{SALAD_ORGANIZATION}/files"
    try:
        response = requests.get(
            url,
            headers={"Salad-Api-Key": SALAD_API_KEY},
            timeout=20,
        )
        logger.info(
            "[PREFLIGHT S4] HTTP %s | organization=%s",
            response.status_code, SALAD_ORGANIZATION
        )
        if not response.ok:
            logger.error("[PREFLIGHT S4 ERROR BODY] %s", response.text[:4000])
            return False
        logger.info("[PREFLIGHT S4] Storage API authorization confirmed.")
        return True
    except Exception as exc:
        logger.error("[PREFLIGHT S4] Authorization check failed: %s", exc)
        return False


def preflight() -> bool:
    if not navigation_regression_self_check():
        return False
    if not consent_and_embedded_cta_regression_self_check():
        return False
    if not mindset_regression_self_check():
        return False
    if not start_gate_regression_self_check():
        return False
    if not i_agree_consent_regression_self_check():
        return False
    if not postcode_and_learning_regression_self_check():
        return False
    if not advanced_controls_regression_self_check():
        return False
    if not question_progression_regression_self_check():
        return False
    if not answer_grounding_regression_self_check():
        return False
    if not terminal_modal_regression_self_check():
        return False
    if not human_input_pets_regression_self_check():
        return False
    if not gender_continue_regression_self_check():
        return False
    if not age_text_entry_regression_self_check():
        return False
    if not birth_date_regression_self_check():
        return False
    if not kb_choice_regression_self_check():
        return False
    if not loyalty_preference_regression_self_check():
        return False
    if not ranking_tier_regression_self_check():
        return False
    if not likert_slider_regression_self_check():
        return False
    if not info_page_scroll_regression_self_check():
        return False
    if not matrix_grid_regression_self_check():
        return False
    if not open_text_min_words_regression_self_check():
        return False
    if not captcha_code_regression_self_check():
        return False
    if not drag_drop_regression_self_check():
        return False
    if not residence_and_close_survey_regression_self_check():
        return False
    if not gender_are_you_inspector_regression_self_check():
        return False
    if not occupation_group_regression_self_check():
        return False
    if not county_dropdown_regression_self_check():
        return False
    if not children_count_regression_self_check():
        return False
    if not child_age_text_regression_self_check():
        return False
    if not select_all_apply_regression_self_check():
        return False
    if not brand_bought_select_all_regression_self_check():
        return False
    if not hovis_unavailable_select_one_regression_self_check():
        return False
    if not rl_generalization_regression_self_check():
        return False
    if not other_brand_followup_regression_self_check():
        return False
    if not bread_brands_text_regression_self_check():
        return False
    if not maxdiff_regression_self_check():
        return False
    if not carousel_row_regression_self_check():
        return False
    if not vlm_stack_regression_self_check():
        return False
    if not discover_device():
        return False

    w, h = get_device_size()
    logger.info("[DEVICE] effective display=%sx%s", w, h)

    foreground = get_foreground_window()
    logger.info("[DEVICE] foreground=%s", foreground)

    if REQUESTED_VISION_MAX_DIM != VISION_MAX_DIM:
        logger.warning(
            "[PREFLIGHT] VISION_MAX_DIM=%s capped to %s for the model's "
            "4096-token context window.",
            REQUESTED_VISION_MAX_DIM, VISION_MAX_DIM,
        )

    if not salad_configured():
        logger.warning("[PREFLIGHT] Salad not configured. Gemini=%s local routers=on.", gemini_configured())
        mark_salad_offline("not configured")
    else:
        if VISION_TRANSPORT not in {"salad_s4", "data_url"}:
            logger.warning("[PREFLIGHT] Unsupported VISION_TRANSPORT=%r; Salad spare disabled.", VISION_TRANSPORT)
            mark_salad_offline(f"bad VISION_TRANSPORT={VISION_TRANSPORT}")
        elif VISION_TRANSPORT == "salad_s4" and not valid_salad_organization(SALAD_ORGANIZATION):
            logger.warning("[PREFLIGHT] Invalid SALAD_ORGANIZATION=%r; Salad spare disabled.", SALAD_ORGANIZATION)
            mark_salad_offline("invalid organization")
        else:
            endpoint = SALAD_URL if SALAD_URL.endswith("/v1/chat/completions") else SALAD_URL + "/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Salad-Api-Key": SALAD_API_KEY}
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json={
                        "model": SALAD_MODEL,
                        "messages": [{"role": "user", "content": "Return the word OK as plain text."}],
                        "max_tokens": 5,
                        "temperature": 0,
                        "stream": False,
                    },
                    timeout=20,
                )
                if not response.ok:
                    logger.warning("[PREFLIGHT TEXT ERROR BODY] %s", response.text[:2000])
                    response.raise_for_status()
                logger.info("[PREFLIGHT] Salad text LLM reachable (spare only).")
            except Exception as exc:
                logger.warning("[PREFLIGHT] Salad text LLM check failed: %s", exc)
                mark_salad_offline(str(exc))

            if _SALAD_ONLINE:
                try:
                    response = requests.post(
                        endpoint,
                        headers=headers,
                        json={
                            "model": SALAD_MODEL,
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Reply with the single word OK after inspecting the image."},
                                    {"type": "image_url", "image_url": {
                                        "url": "https://salad-benchmark-assets.download/coco2017/train2017/000000000094.jpg"
                                    }},
                                ],
                            }],
                            "max_tokens": 10,
                            "temperature": 0,
                            "stream": False,
                        },
                        timeout=30,
                    )
                    if not response.ok:
                        logger.warning("[PREFLIGHT VISION ERROR BODY] %s", response.text[:2000])
                        response.raise_for_status()
                    logger.info("[PREFLIGHT] Salad multimodal reachable (spare).")
                except Exception as exc:
                    logger.warning("[PREFLIGHT] Salad multimodal check failed: %s", exc)
                    mark_salad_offline(str(exc))

                if _SALAD_ONLINE and VISION_TRANSPORT == "salad_s4" and not preflight_s4_access():
                    logger.warning("[PREFLIGHT] S4 access failed; Salad spare disabled.")
                    mark_salad_offline("S4 authorization failed")

    gemini_ok = False
    if gemini_configured():
        models = []
        for name in (GEMINI_LITE_MODEL, *GEMINI_LITE_FALLBACKS, GEMINI_FLASH_MODEL, *GEMINI_FLASH_FALLBACKS):
            if name and name not in models:
                models.append(name)
        for model_name in models[:4]:
            try:
                response = requests.post(
                    f"{GEMINI_BASE_URL}/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {GEMINI_API_KEY}"},
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": "Reply with OK"}],
                        "max_tokens": 4,
                        "temperature": 0,
                    },
                    timeout=20,
                )
                if response.ok:
                    logger.info("[PREFLIGHT] Gemini reachable model=%s", model_name)
                    gemini_ok = True
                    break
                if response.status_code == 404:
                    logger.warning("[PREFLIGHT] Gemini model %s 404; trying next name.", model_name)
                    continue
                logger.warning("[PREFLIGHT] Gemini %s HTTP %s %s", model_name, response.status_code, response.text[:400])
            except Exception as exc:
                logger.warning("[PREFLIGHT] Gemini %s failed: %s", model_name, exc)
        if not gemini_ok:
            logger.warning("[PREFLIGHT] GEMINI_API_KEY set but no Gemini model answered.")
    else:
        logger.warning("[PREFLIGHT] GEMINI_API_KEY missing. Salad-only if Salad is up.")

    logger.info(
        "[PREFLIGHT] command stack: local -> salad -> gemini-lite -> gemini-flash | salad_online=%s gemini=%s primary=%s",
        _SALAD_ONLINE, gemini_ok or gemini_configured(), VLM_PRIMARY,
    )
    if not _SALAD_ONLINE and not gemini_configured():
        logger.error("[PREFLIGHT] Neither Salad nor Gemini is available.")
        return False
    logger.info("[PREFLIGHT] Device checks passed.")
    return True
