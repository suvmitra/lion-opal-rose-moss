# 16_inspect.py — shared engine namespace (do not import directly)

def apply_authorized_personal_fallback(
    decision: dict[str, Any], obs: Observation
) -> dict[str, Any]:
    """Recover a missing-fact/escape decision from user-configured KB fallbacks."""
    if obs.screen_phase != "survey_question" or not ALLOW_PERSONAL_INFERENCE:
        return decision

    action = str(decision.get("action") or "").lower()
    target_text = str(decision.get("target_text") or "").lower()
    needs_recovery = action == "request_human" or "can't answer" in target_text or "cannot answer" in target_text
    if not needs_recovery:
        return decision

    fallbacks = obs.kb.get("personal_question_fallbacks")
    if not isinstance(fallbacks, dict):
        return decision

    question = " ".join([
        str(decision.get("question_text") or ""),
        obs.ocr_text,
    ]).lower()

    for fallback_key, fallback in fallbacks.items():
        if not isinstance(fallback, dict):
            continue
        keywords = fallback.get("question_keywords") or []
        if isinstance(keywords, str):
            keywords = [keywords]
        normalized = [str(term).strip().lower() for term in keywords if str(term).strip()]
        if not normalized or not all(term in question for term in normalized):
            continue

        answer_value = fallback.get("answer")
        if isinstance(answer_value, (list, tuple)):
            continue
        answer = str(answer_value or "").strip()
        if not answer:
            continue
        matched_node = text_match_node(obs.ui_nodes, answer)
        confidence = float(fallback.get("confidence", 0.65))
        source_basis = str(
            fallback.get("source_basis")
            or "User-authorized personal inference configured in knowledge_base.json"
        )
        resolved_key = canonical_key(str(fallback.get("kb_key") or fallback_key))
        needs_kb_write = PERSIST_INFERRED_ANSWERS and obs.kb.get(resolved_key) != answer
        logger.warning(
            "[PERSONAL FALLBACK] Replacing %s with inferred answer %r for kb_key=%s",
            action or "escape answer", answer, fallback_key
        )
        return {
            **decision,
            "answer_reason": source_basis,
            "action": "select_option",
            "target_element_id": matched_node["id"] if matched_node else None,
            "target_text": answer,
            "target_coords": None,
            "input_payload": answer,
            "kb_key": resolved_key,
            "kb_write": needs_kb_write,
            "missing_fact_key": None,
            "confidence_score": max(LOW_CONFIDENCE, confidence),
            "postcondition": f"selected option is {answer}",
            "visual_reasoning": (
                "A substantive visible option matches the configured personal fallback; "
                "the underlined escape link is not a selected answer."
            ),
            "answer_provenance": "inferred",
            "source_basis": source_basis,
            "inference_confidence": confidence,
        }

    return decision


def normalize_choice(text: str) -> str:
    value = str(text or "").lower().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def kb_option_match(option: str, answer: str) -> bool:
    """True when a visible option is the same fact as a KB/persona value."""
    left, right = normalize_choice(option), normalize_choice(answer)
    if not left or not right:
        return False
    if re.fullmatch(r"\d+", left) or re.fullmatch(r"\d+", right):
        return left == right
    if left == right or left in right or right in left:
        return True
    left_tokens, right_tokens = set(left.split()), set(right.split())
    if len(left_tokens) >= 2 and (left_tokens <= right_tokens or right_tokens <= left_tokens):
        return True
    return False


EXACT_KB_QUESTION_HINTS: dict[str, tuple[str, ...]] = {
    "country": ("where are you living", "where do you live", "country of residence", "which country"),
    "smoking_status": ("smoke", "smoking", "tobacco", "vape"),
    "flight_types": ("when you fly", "types of flights"),
    "county": ("following counties", "which county", "counties do you currently"),
    "occupation_group": ("occupational group", "chief income earner"),
    "employment_status": ("employment status", "employed", "work full time"),
    "industry": ("industry", "sector do you work"),
    "education": ("education", "highest degree", "qualification"),
    "marital_status": ("marital status", "married"),
    "gender": ("gender", "identify as", "are you?"),
    "number_of_children": ("how many dependent children", "how many children", "dependent children", "children under 18"),
    "has_children": ("do you have children", "have any children"),
    "housing": ("housing", "rent or own", "living arrangement"),
    "primary_transport": ("transport", "commute"),
    "webcam_interview_willingness": ("webcam interview", "willing to participate"),
    "household_pets": ("pets currently live", "which of these pets"),
    "household_income": ("annual income", "household's total annual income"),
    "loyalty_program_openness": ("loyalty program", "joining loyalty"),
}


def exact_kb_option_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Select a visible option that exactly matches a relevant scalar KB fact."""
    if obs.screen_phase != "survey_question":
        return None
    question = re.sub(r"\s+", " ", obs.ocr_text.lower())
    for kb_key, hints in EXACT_KB_QUESTION_HINTS.items():
        if not any(hint in question for hint in hints):
            continue
        answer = obs.kb.get(kb_key)
        if not isinstance(answer, (str, int, float, bool)):
            continue
        answer_text = str(answer).strip()
        if not answer_text:
            continue
        visible_label = None
        for option in option_labels_from_observation(obs):
            if kb_option_match(option, answer_text):
                visible_label = option
                break
        if visible_label:
            answer_text = visible_label
        matched = option_node_for_text(obs, answer_text) or text_match_node(
            obs.ui_nodes, visible_label or answer_text
        )
        if matched and in_header_chrome(matched.get("bounds") or [], obs.image_height):
            matched = None
        coords = body_option_coords(obs, answer_text) if gender_choice_screen(obs) else None
        visible = bool(visible_label) or answer_text.lower() in question
        if not matched and not visible and not coords:
            continue

        metadata = obs.kb.get("answer_metadata")
        item_metadata = metadata.get(kb_key, {}) if isinstance(metadata, dict) else {}
        provenance = str(item_metadata.get("provenance") or "declared").lower()
        if provenance not in {"verified", "declared", "inferred"}:
            provenance = "declared"
        confidence = float(item_metadata.get("confidence") or 0.99)
        logger.info(
            "[EXACT KB ROUTER] question matched kb_key=%s answer=%r node=%s",
            kb_key, answer_text, matched.get("id") if matched else None,
        )
        return {
            "screen_state": "survey_question",
            "question_text": obs.ocr_text,
            "answer_reason": f"Exact visible option matches knowledge-base fact {kb_key}.",
            "action": "select_option",
            "target_element_id": matched.get("id") if matched else None,
            "target_text": answer_text,
            "target_coords": coords,
            "coordinate_authoritative": bool(coords),
            "input_payload": answer_text,
            "kb_key": kb_key,
            "kb_write": False,
            "missing_fact_key": None,
            "confidence_score": max(0.90, confidence),
            "postcondition": f"selected option is {answer_text}",
            "visual_reasoning": "The answer text exactly matches a currently visible option.",
            "answer_provenance": provenance,
            "source_basis": f"knowledge_base.json:{kb_key}",
            "inference_confidence": confidence,
        }
    return None


def configured_personal_answer_decision(
    obs: Observation,
) -> Optional[dict[str, Any]]:
    """Resolve an explicit KB question mapping before spending the VLM context."""
    exact = exact_kb_option_decision(obs)
    if exact:
        return exact

    normalized_question = re.sub(r"\s+", " ", obs.ocr_text.lower())
    if "webcam" in normalized_question and "willing" in normalized_question:
        answer = (
            "Yes, I would be willing"
            if WEBCAM_INTERVIEW_WILLING
            else "No, I would not be willing to participate"
        )
        matched = text_match_node(obs.ui_nodes, answer)
        visible_option = answer.lower() in normalized_question or (
            WEBCAM_INTERVIEW_WILLING
            and "yes," in normalized_question
            and "would be willing" in normalized_question
        ) or (
            not WEBCAM_INTERVIEW_WILLING
            and "no," in normalized_question
            and "not be willing" in normalized_question
        )
        if matched or visible_option:
            logger.info(
                "[DECLARED PREFERENCE ROUTER] webcam_interview_willingness=%s target=%r node=%s",
                WEBCAM_INTERVIEW_WILLING, answer, matched.get("id") if matched else None,
            )
            return {
                "screen_state": "survey_question",
                "question_text": obs.ocr_text,
                "answer_reason": "User-declared webcam-interview willingness preference.",
                "action": "select_option",
                "target_element_id": matched.get("id") if matched else None,
                "target_text": answer,
                "target_coords": None,
                "input_payload": answer,
                "kb_key": "webcam_interview_willingness",
                "kb_write": obs.kb.get("webcam_interview_willingness") != answer,
                "missing_fact_key": None,
                "confidence_score": 0.99,
                "postcondition": f"selected option is {answer}",
                "visual_reasoning": "The configured declared preference exactly matches a visible answer option.",
                "answer_provenance": "declared",
                "source_basis": "WEBCAM_INTERVIEW_WILLING configuration set from explicit user direction",
                "inference_confidence": 0.99,
            }

    seed = {
        "screen_state": "survey_question",
        "question_text": obs.ocr_text,
        "answer_reason": "Checking configured personal answer mappings.",
        "action": "request_human",
        "target_element_id": None,
        "target_text": None,
        "target_coords": None,
        "input_payload": None,
        "kb_key": None,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.0,
        "postcondition": "",
        "visual_reasoning": "",
        "answer_provenance": "declared",
        "source_basis": "",
        "inference_confidence": 0.0,
    }
    resolved = apply_authorized_personal_fallback(seed, obs)
    if str(resolved.get("action") or "").lower() == "request_human":
        return None
    logger.info(
        "[ANSWER ROUTER] Reused configured personal answer kb_key=%s target=%r",
        resolved.get("kb_key"), resolved.get("target_text")
    )
    return resolved


# ------------------------------------------------------------------------------
# Interactive human key-in for unresolved personal questions (v24.0.17)
# ------------------------------------------------------------------------------

_MULTI_SELECT_PROGRESS: dict[str, list[str]] = {}
_HUMAN_PROMPTED_SIGNATURES: set[str] = set()
_HUMAN_PROMPTED_KEYS: set[str] = set()
_PROGRESSION_SCROLLS: dict[str, int] = {}
_LAST_SELECT_FINGERPRINT: dict[str, str] = {}
_INFO_SCROLLS: dict[str, int] = {}
_RANK_PROGRESS: dict[str, list[str]] = {}
_COUNTY_OPEN_TRIES: dict[str, int] = {}
_CHILDREN_TAPPED: dict[str, str] = {}
_CHILDREN_SCROLLS: dict[str, int] = {}
_CHILD_AGE_TYPED: dict[str, str] = {}
_SALAD_ONLINE = True
_OPEN_TEXT_TYPED: dict[str, str] = {}
_OPEN_TEXT_DONE: dict[str, bool] = {}
_VLM_STATE: dict[str, Any] = {"spend": [], "prefer_flash": False, "dead_models": set()}
VLM_PRICES_USD = {
    "gemini-lite": {"input": 0.10, "output": 0.40},
    "gemini-flash": {"input": 0.30, "output": 2.50},
    "salad": {"input": 0.0, "output": 0.0},
}
_LIKERT_PROGRESS: dict[str, list[str]] = {}
_CAPTCHA_TYPED: dict[str, str] = {}
_DRAG_DONE: dict[str, bool] = {}
_LIKERT_SCROLLS: dict[str, int] = {}


def collapse_option_fragments(labels: list[str]) -> list[str]:
    """Drop OCR fragments that are already contained in a longer option."""
    kept: list[str] = []
    for label in labels:
        lowered = label.lower()
        if any(
            lowered != other.lower()
            and lowered in other.lower()
            and len(other) >= len(label) + 10
            for other in labels
        ):
            continue
        kept.append(label)
    return kept or labels


def longest_option_containing(options: list[str], term: str) -> Optional[str]:
    matches = [option for option in options if term.lower() in option.lower()]
    return max(matches, key=len) if matches else None


def option_labels_from_observation(obs: Observation) -> list[str]:
    if occupation_group_question_visible(obs.ocr_text):
        occupation = occupation_option_labels(obs.ocr_text)
        if occupation:
            return occupation
    if children_count_question_visible(obs.ocr_text):
        numeric = numeric_radio_labels(obs)
        if numeric:
            return numeric
    node_labels = [node_text(node) for node in obs.ui_nodes if node_text(node)]
    labels = collapse_option_fragments(visible_answer_option_labels(obs.ocr_text, node_labels))
    return [
        label for label in labels
        if not is_chrome_option_label(label) and not is_banner_or_instruction_label(label)
    ]


def current_question_text(obs: Observation) -> str:
    question = question_text_from_ocr(obs.ocr_text)
    return question or _normalize_ocr_question(obs.ocr_text)


def _normalize_ocr_question(ocr_text: str) -> str:
    text = re.sub(r"\s+", " ", str(ocr_text or "")).strip()
    if "?" in text:
        return text[: text.rfind("?") + 1]
    return text[:240]


def observation_kb_key(obs: Observation) -> str:
    if county_question_visible(obs.ocr_text):
        return "county"
    if occupation_group_question_visible(obs.ocr_text):
        return "occupation_group"
    if children_count_question_visible(obs.ocr_text):
        return "number_of_children"
    return canonical_key(derive_question_kb_key(current_question_text(obs), EXACT_KB_QUESTION_HINTS))


def selected_option_labels(obs: Observation) -> set[str]:
    selected: set[str] = set()
    signature = semantic_screen_signature(obs)
    for label in _MULTI_SELECT_PROGRESS.get(signature, []):
        selected.add(label.lower())
    for node in obs.ui_nodes:
        if not (node.get("checked") or node.get("selected")):
            continue
        label = node_text(node)
        if label:
            selected.add(label.lower())
    return selected


def record_multi_select_progress(obs: Observation, label: str) -> None:
    if not label:
        return
    signature = semantic_screen_signature(obs)
    done = _MULTI_SELECT_PROGRESS.setdefault(signature, [])
    if label not in done:
        done.append(label)


def stored_intended_options(obs: Observation) -> list[str]:
    if obs.screen_phase != "survey_question":
        return []
    options = option_labels_from_observation(obs)
    if not options:
        return []
    kb_key = observation_kb_key(obs)
    intended = intended_options_from_kb_value(obs.kb.get(kb_key))
    if not intended:
        fallbacks = obs.kb.get("personal_question_fallbacks")
        if isinstance(fallbacks, dict):
            fallback = fallbacks.get(kb_key)
            if isinstance(fallback, dict):
                intended = intended_options_from_kb_value(fallback.get("answer"))
    if not intended:
        return []
    grounded: list[str] = []
    seen: set[str] = set()
    for item in intended:
        status, matched = parse_human_answer_input(str(item), options)
        if status != "ok":
            continue
        for label in matched:
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            grounded.append(label)
    return grounded


def remaining_intended_options(obs: Observation, intended: list[str]) -> list[str]:
    selected = selected_option_labels(obs)
    remaining: list[str] = []
    for label in intended:
        keys = {label.lower()} | option_match_keys(label)
        if keys & selected:
            continue
        remaining.append(label)
    return remaining


def grounded_option_decision(
    obs: Observation,
    target_text: str,
    *,
    kb_key: str,
    intended: list[str],
    remaining_after: list[str],
    reason: str,
    provenance: str = "declared",
    source_basis: str = "",
) -> dict[str, Any]:
    matched_node = text_match_node(obs.ui_nodes, target_text)
    complete = not remaining_after
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": reason,
        "action": "select_option" if not complete or remaining_after or target_text else "click",
        "target_element_id": matched_node["id"] if matched_node else None,
        "target_text": target_text,
        "target_coords": None,
        "input_payload": intended if len(intended) != 1 else intended[0],
        "kb_key": kb_key,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.99,
        "postcondition": f"selected option is {target_text}",
        "visual_reasoning": reason,
        "answer_provenance": provenance,
        "source_basis": source_basis or f"knowledge_base.json:{kb_key}",
        "inference_confidence": 1.0,
        "selection_complete": complete,
        "intended_options": intended,
    }


def configured_multi_option_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tick the next stored multi-select answer, or advance when all are done."""
    if obs.screen_phase != "survey_question":
        return None
    if occupation_group_question_visible(obs.ocr_text):
        return None
    if matrix_grid_visible(obs):
        return None
    intended = stored_intended_options(obs)
    if not intended:
        return None
    remaining = remaining_intended_options(obs, intended)
    kb_key = observation_kb_key(obs)
    signature = question_fingerprint(obs)
    last_select = (
        _LAST_SELECT_FINGERPRINT.get(signature, "")
        or _LAST_SELECT_FINGERPRINT.get(semantic_screen_signature(obs), "")
    )
    if remaining and last_select:
        remaining = [
            label for label in remaining
            if label.lower() != last_select
            and last_select not in option_match_keys(label)
        ]
    if not remaining:
        logger.info(
            "[MULTI KB] All stored options are selected for kb_key=%s: %s",
            kb_key, intended,
        )
        return survey_next_decision(obs)
    target = remaining[0]
    after = remaining[1:]
    logger.info(
        "[MULTI KB] Selecting %r for kb_key=%s remaining=%s",
        target, kb_key, after,
    )
    return grounded_option_decision(
        obs,
        target,
        kb_key=kb_key,
        intended=intended,
        remaining_after=after,
        reason="Stored knowledge-base answers match visible options on this screen.",
        provenance="declared",
        source_basis=f"knowledge_base.json:{kb_key}",
    )

def gender_choice_screen(obs: Observation) -> bool:
    blob = re.sub(r"[\s|]+", " ", str(obs.ocr_text or "").lower())
    labels = " ".join(str(item).lower() for item in option_labels_from_observation(obs))
    nodes = " ".join(node_text(n).lower() for n in obs.ui_nodes)
    combined = f"{blob} {labels} {nodes}"
    return bool(re.search(r"\bmale\b", combined) and "female" in combined)

def inspect_decision(obs: Observation, decision: dict[str, Any]) -> dict[str, Any]:
    if not decision:
        return decision
    action = str(decision.get("action") or "").lower()
    target = str(decision.get("target_text") or "")
    if i_agree_consent_visible(obs.ocr_text):
        fill = i_agree_consent_decision(obs)
        if fill:
            logger.warning("[INSPECTOR] Consent screen; %s not %r.", fill.get("target_text"), target)
            return fill
    if start_gate_visible(obs.ocr_text) and "start" not in target.lower():
        fill = navigation_cta_decision(obs)
        if fill and "start" in str(fill.get("target_text") or "").lower():
            logger.warning("[INSPECTOR] Start! gate; tap Start! not %r.", target)
            return fill
    if obs.screen_phase not in {"survey_question", "navigation", "survey_landing"}:
        return decision
    if float(decision.get("confidence_score") or 0) >= 0.9 and (
        decision.get("maxdiff_side")
        or decision.get("maxdiff_done")
        or decision.get("select_all_pick")
        or decision.get("select_all_done")
        or (action == "scroll_down" and maxdiff_question_visible(obs.ocr_text))
        or (action == "scroll_down" and select_all_apply_visible(obs.ocr_text))
    ):
        return decision

    if is_banner_or_instruction_label(target) or (
        is_chrome_option_label(target) and not is_progression_cta(target)
    ):
        alt = exact_kb_option_decision(obs) or inferred_preference_decision(obs)
        if alt and not is_banner_or_instruction_label(str(alt.get("target_text") or "")):
            logger.warning("[INSPECTOR] Rejected banner/chrome target %r; using %r",
                           target[:80], alt.get("target_text"))
            return alt
    fill = gender_screen_decision(obs)
    if fill:
        logger.info("[INSPECTOR] Gender %s at %s", fill.get("target_text"), fill.get("target_coords"))
        return fill
    if gender_choice_screen(obs) and action in {"click"} and is_progression_cta(target) and (
        survey_validation_error(obs) or required_answer_missing(obs)
    ):
        alt = exact_kb_option_decision(obs)
        if alt:
            logger.warning("[INSPECTOR] Gender unanswered; tap %r before Continue.", alt.get("target_text"))
            return alt

    if county_question_visible(obs.ocr_text):
        fill = county_dropdown_decision(obs)
        if fill:
            if action in {"click"} and is_progression_cta(target) and not county_selection_complete(obs):
                logger.warning("[INSPECTOR] County incomplete; %s instead of Continue.", fill.get("action"))
                return fill
            if action in {"select_option"} and county_dropdown_open(obs.ocr_text):
                if intended_county(obs).lower() not in (target or "").lower():
                    logger.warning("[INSPECTOR] Rejected county %r; want %s.", target, intended_county(obs))
                    return fill

    if children_count_question_visible(obs.ocr_text):
        fill = dependent_children_decision(obs)
        if fill:
            if not children_pick_complete(obs):
                if action != "select_option" or not str(target).strip().isdigit():
                    logger.warning("[INSPECTOR] Children unanswered; tap %s not %s.",
                                   fill.get("target_text"), action)
                    return fill
            elif action in {"select_option", "wait", "click"} and fill.get("action") != action:
                logger.warning("[INSPECTOR] Children already tapped; %s instead of %s.",
                               fill.get("action"), action)
                return fill

    if child_ages_question_visible(obs.ocr_text):
        fill = child_age_text_decision(obs)
        if fill and str(fill.get("action") or "") != action:
            logger.warning("[INSPECTOR] Child-age needs %s not %s.", fill.get("action"), action)
            return fill

    if carousel_row_question_visible(obs.ocr_text):
        fill = carousel_row_decision(obs)
        if fill and (
            str(fill.get("action") or "") != action
            or str(fill.get("target_text") or "").lower() != str(target or "").lower()
        ):
            logger.warning("[INSPECTOR] Carousel needs %s %r, not %s %r.",
                           fill.get("action"), fill.get("target_text"), action, target)
            return fill

    if maxdiff_question_visible(obs.ocr_text):
        fill = maxdiff_decision(obs)
        if fill and (
            str(fill.get("action") or "") != action
            or str(fill.get("target_text") or "").lower() != str(target or "").lower()
        ):
            logger.warning("[INSPECTOR] MaxDiff needs %s %r, not %s %r.",
                           fill.get("action"), fill.get("target_text"), action, target)
            return fill

    if occupation_group_question_visible(obs.ocr_text):
        fill = occupation_group_decision(obs)
        if fill and str(fill.get("action") or "") == "select_option":
            if action in {"click"} and is_progression_cta(target):
                logger.warning("[INSPECTOR] Occupation unanswered; tap %r before Continue.", fill.get("target_text"))
                return fill
            if action in {"select_option"} and is_banner_or_instruction_label(target):
                return fill
            if action in {"select_option"} and "administrative" in target.lower() and "managerial" not in target.lower():
                logger.warning("[INSPECTOR] Rejected OCR fragment %r; using occupation %r", target, fill.get("target_text"))
                return fill

    if county_question_visible(obs.ocr_text) and action in {"open_dropdown", "select_option"}:
        if county_selection_complete(obs):
            logger.warning("[INSPECTOR] Combo already shows %s; Continue instead of %s.",
                           intended_county(obs), action)
            cont = county_dropdown_decision(obs)
            return cont if cont and str(cont.get("action")) == "click" else {
                "action": "click", "target_text": "Continue »", "target_coords": [500, 610],
                "coordinate_authoritative": True, "confidence_score": 0.96,
                "postcondition": "screen changed", "kb_key": "county",
                "selection_complete": True,
            }

    if survey_validation_error(obs) and action in {"click"} and is_progression_cta(target):
        if county_question_visible(obs.ocr_text) and county_selection_complete(obs):
            return decision
        if children_count_question_visible(obs.ocr_text) and children_pick_complete(obs):
            return decision
        if looks_like_single_choice(obs.ocr_text) or hovis_unavailable_visible(obs.ocr_text):
            if _SELECT_ONE_SESSION.get("verified"):
                logger.warning("[INSPECTOR] Select-one already tapped; Continue despite the red banner.")
                return decision
            fill = single_choice_radio_decision(obs)
            if fill and str(fill.get("action") or "") in {"select_option", "select_then_continue", "focus_select_continue"}:
                logger.warning("[INSPECTOR] Select-one needs %s %r, not Continue.",
                               fill.get("action"), fill.get("target_text"))
                return fill
        alt = exact_kb_option_decision(obs) or inferred_preference_decision(obs) or (
            county_dropdown_decision(obs) if county_question_visible(obs.ocr_text) else None
        )
        if alt and not is_progression_cta(str(alt.get("target_text") or "")):
            if not (county_question_visible(obs.ocr_text) and county_selection_complete(obs)):
                logger.warning("[INSPECTOR] Red error still visible; fill %r instead of Continue.",
                               alt.get("target_text"))
                return alt
    return decision


def wh_supervisor_decision(
    obs: Observation,
    *,
    issue: str,
    last_action: str = "",
    last_target: str = "",
) -> Optional[dict[str, Any]]:
    """Ask Gemini/Salad WHO-WHAT-WHY-HOW-WHEN for one recovery action instead of looping."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return None
    if not gemini_configured() and not (salad_configured() and _SALAD_ONLINE):
        logger.warning("[WH] No VLM backend; skipping supervisor prompt.")
        return None
    prompt = (
        "WHO: You supervise an Android survey-filling agent.\n"
        "WHAT: Inspect the screenshot. County question. Knowledge base city is Dublin.\n"
        f"WHY: Local router stalled ({issue}). Last action={last_action!r} target={last_target!r}.\n"
        "HOW: Return ONE JSON action. If the combo already shows Dublin, click Continue » "
        "at the green button. If the list is open and Dublin is visible, tap Dublin. "
        "If the list starts after Dublin, scroll_up with list_scroll true. "
        "Do not open_dropdown on 'Select one...' when Dublin is already selected.\n"
        "WHEN: Now. One atomic action.\n"
        f"OCR: {(obs.ocr_text or '')[:900]}\n"
        f"UI: {json.dumps([{'t': node_text(n), 'i': n.get('id')} for n in (obs.ui_nodes or [])[:18]], ensure_ascii=False)[:1200]}"
    )
    compact = (
        "JSON only. If Dublin is selected click Continue ». "
        'Example {"action":"click","target_text":"Continue »","target_coords":[500,610],'
        '"coordinate_authoritative":true,"confidence_score":0.9,"postcondition":"screen changed"}'
    )
    try:
        raw, backend = call_vlm(prompt, Path(obs.screenshot), compact, prefer_flash=True)
        logger.info("[WH] backend=%s raw=%s", backend, raw[:1500])
        data = parse_json_response(raw)
        data.setdefault("confidence_score", 0.9)
        data.setdefault("postcondition", "screen changed")
        data["wh_supervisor"] = True
        return data
    except Exception as exc:
        logger.warning("[WH] Supervisor VLM failed: %s", exc)
        return None


def prefer_progression_over_repeat(
    decision: dict[str, Any],
    obs: Observation,
    stagnation_count: int = 0,
) -> dict[str, Any]:
    if obs.screen_phase != "survey_question" or not decision:
        return decision
    action = str(decision.get("action") or "").lower()
    target = str(decision.get("target_text") or "").strip()
    if is_forbidden_progression_target(target) and action in {"click", "select_option"}:
        logger.warning(
            "[PROGRESSION REPAIR] Vetoed forbidden target %r; grounding Continue/Next.",
            target,
        )
        alt = None
        if "close" in cta_core(target):
            alt = exact_kb_option_decision(obs) or inferred_preference_decision(obs)
        if alt and not is_forbidden_progression_target(str(alt.get("target_text") or "")):
            return alt
        return survey_next_decision(obs)
    intended = stored_intended_options(obs)
    if intended and action in {"click", "select_option"} and target:
        allowed = False
        for label in intended:
            status, matched = parse_human_answer_input(target, [label])
            if status == "ok" and matched:
                allowed = True
                break
        if not allowed and not is_progression_cta(target):
            remaining = remaining_intended_options(obs, intended)
            logger.warning(
                "[KB REPAIR] Rejected %r because stored answers are %s",
                target, intended,
            )
            if remaining:
                return grounded_option_decision(
                    obs, remaining[0], kb_key=observation_kb_key(obs),
                    intended=intended, remaining_after=remaining[1:],
                    reason="Stored knowledge-base answers take precedence over a contradictory model click.",
                )
            return survey_next_decision(obs)
    if action in {"type_text", "type_comment"}:
        key = question_fingerprint(obs)
        already = (
            _OPEN_TEXT_TYPED.get(key)
            or _OPEN_TEXT_TYPED.get(open_text_screen_key(obs))
            or _OPEN_TEXT_DONE.get(open_text_screen_key(obs))
            or open_text_box_has_answer(obs)
        )
        payload = str(decision.get("input_payload") or "")
        if already or (payload and payload[:12].lower() in (obs.ocr_text or "").lower()):
            logger.info("[PROGRESSION REPAIR] Text already typed; Continue instead of re-tapping the box/keyboard.")
            return survey_next_decision(obs) or decision
    if action in {"click", "select_option", "toggle_checkbox"} and target and not is_progression_cta(target):
        selected = selected_option_labels(obs)
        keys = {target.lower()} | option_match_keys(target)
        already = bool(keys & selected)
        last = (
            _LAST_SELECT_FINGERPRINT.get(question_fingerprint(obs), "")
            or _LAST_SELECT_FINGERPRINT.get(semantic_screen_signature(obs), "")
        )
        same_as_last = bool(last and (last == target.lower() or last in keys))
        if already or same_as_last or stagnation_count >= 1:
            if carousel_row_question_visible(obs.ocr_text):
                fill = carousel_row_decision(obs)
                if fill:
                    logger.info(
                        "[PROGRESSION REPAIR] Carousel keeps %s %r, not Continue.",
                        fill.get("action"), fill.get("target_text"),
                    )
                    return fill
            if required_answer_missing(obs):
                inferred = inferred_preference_decision(obs)
                if inferred:
                    return inferred
            if select_all_apply_visible(obs.ocr_text):
                fill = select_all_apply_decision(obs)
                if fill and (select_all_lime_band_count(obs) >= 1 or fill.get("action") != "click"):
                    logger.info("[PROGRESSION REPAIR] Select-all %s.", fill.get("action"))
                    if not (select_all_lime_band_count(obs) < 1 and fill.get("action") == "click"):
                        return fill
            logger.info(
                "[PROGRESSION REPAIR] Option %r already issued; clicking Continue instead of toggling it off.",
                target,
            )
            return survey_next_decision(obs)
    return decision
