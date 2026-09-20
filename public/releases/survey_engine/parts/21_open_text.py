# 21_open_text.py — shared engine namespace (do not import directly)



def captcha_next_decision(obs: Observation) -> dict[str, Any]:
    """Click the visible Next bar. Never BACK, never an unlabeled node."""
    target = None
    for node in obs.ui_nodes:
        if node.get("enabled") and is_progression_cta(node_text(node)):
            target = node
            break
    label = node_text(target) if target else (visible_progression_label(obs.ocr_text) or "Next")
    coords = [500, 500] if soft_keyboard_visible(obs) else [500, 760]
    if obs.screenshot and Path(obs.screenshot).exists():
        center = ocr_text_center(Path(obs.screenshot), "Next")
        if center and center[1] >= obs.image_height * 0.35:
            coords = [
                int(max(80, min(920, center[0] * 1000 / max(1, obs.image_width)))),
                int(max(400, min(900, center[1] * 1000 / max(1, obs.image_height)))),
            ]
    logger.info("[CTA] Clicking Next node=%s coords=%s", target.get("id") if target else None, coords)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": "Captcha is already in the box; tap Next.",
        "action": "click",
        "target_element_id": target.get("id") if target else None,
        "target_text": label or "Next",
        "target_coords": coords,
        "coordinate_authoritative": True,
        "input_payload": None,
        "kb_key": "captcha_code",
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.95,
        "postcondition": "screen changed",
        "visual_reasoning": "The Next bar is enabled once the code is typed.",
        "answer_provenance": "verified",
        "source_basis": "Typed captcha + visible Next control",
        "inference_confidence": 0.95,
    }


def captcha_code_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Type the on-screen captcha into the box, then Next. Never treat as a matrix."""
    if not captcha_code_question_visible(obs.ocr_text):
        _CAPTCHA_TYPED.pop("captcha_code", None)
        return None
    if captcha_field_complete(obs):
        logger.info("[CAPTCHA] Code already typed; grounding Next.")
        return captcha_next_decision(obs)
    code = (
        captcha_code_from_image(obs)
        or captcha_code_from_ocr_text(obs.ocr_text)
        or captcha_code_from_vlm(obs)
    )
    if not looks_like_captcha_code(code):
        logger.warning("[CAPTCHA] Code not readable yet; waiting to retry.")
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Captcha is visible but the distorted code was not read yet.",
            "action": "wait",
            "confidence_score": 0.4,
            "postcondition": "screen stable for re-observation",
        }
    coords = captcha_field_coords(obs)
    logger.info("[CAPTCHA] Typing code=%r coords=%s", code, coords)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Type the on-screen code {code} into the text box.",
        "action": "type_text",
        "target_element_id": None,
        "target_text": "captcha input",
        "target_coords": coords,
        "input_payload": code,
        "kb_key": "captcha_code",
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.9,
        "postcondition": f"field contains {code}",
        "visual_reasoning": "The page asks to type the distorted code, then Next.",
        "answer_provenance": "inferred",
        "source_basis": "Captcha image + OCR/VLM",
        "inference_confidence": 0.8,
        "coordinate_authoritative": True,
    }


def open_text_question_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if captcha_code_question_visible(ocr_text):
        return False
    if ranking_question_visible(ocr_text) or likert_slider_question_visible(ocr_text):
        return False
    if select_all_apply_visible(ocr_text):
        return False
    hints = (
        "type your answer", "at least 5 words", "words long", "in your own words",
        "write a", "please describe", "comment box", "tell us what",
        "three things you like", "role model",
        "be as specific as possible", "brands of bread", "brands of breads",
        "what brands", "please state what", "any other brand", "any other",
        "please provide an answer", "think of?",
    )
    return any(token in text for token in hints) and (
        "?" in text or "type your" in text or "words" in text
    )


def min_words_required(ocr_text: str) -> int:
    match = re.search(r"at least\s+(\d+)\s+words", str(ocr_text or "").lower())
    if match:
        return int(match.group(1))
    if "words long" in str(ocr_text or "").lower():
        return 5
    return 5 if open_text_question_visible(ocr_text) else 0


def open_text_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]{2,}", str(text or "")))


def open_text_current_value(obs: Observation) -> str:
    for node in obs.ui_nodes:
        if node.get("editable"):
            value = node_text(node).strip()
            if value and "type your answer" not in value.lower():
                return value
    blob = str(obs.ocr_text or "")
    skip = (
        "what are", "type your", "please enter", "privacy", "english", "survey",
        "please be", "as specific", "please state", "brands of", "aware of",
        "continue", "accessibility", "select all",
        "please provide", "problems with", "there were", "any other",
        "think of", "brennans", "johnston", "data you entered", "errors below",
    )
    lines = []
    for raw in blob.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if not line or any(token in lowered for token in skip):
            continue
        if re.fullmatch(r"[\d:%]+", line.replace(" ", "")):
            continue
        lines.append(line)
    return " ".join(lines[:4])


def open_text_screen_key(obs: Observation) -> str:
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if "any other" in blob and "brand" in blob:
        return "bread_brands_other"
    if "brands of bread" in blob or "brands of breads" in blob:
        return "bread_brands_aware"
    return question_fingerprint(obs)


def open_text_is_garbage(text: str) -> bool:
    blob = str(text or "").lower()
    return any(token in blob for token in (
        "clear and useful", "minimum word requirement", "written answer that meets",
        "this is a clear",
    ))


def open_text_box_has_answer(obs: Observation) -> bool:
    blob = str(obs.ocr_text or "").lower()
    current = open_text_current_value(obs).lower()
    if any(token in current for token in ("batch", "pat the baker", "supervalu")):
        return True
    if "any other" in blob and any(token in blob for token in ("batch", "pat the baker", "supervalu")):
        return True
    typed = _OPEN_TEXT_TYPED.get(open_text_screen_key(obs), "")
    if typed and not open_text_is_garbage(typed):
        return True
    if open_text_word_count(current) >= 3 and not open_text_is_garbage(current):
        return True
    return False


def open_text_sentence(obs: Observation, minimum: int) -> str:
    blob = (str(obs.ocr_text or "") + " " + current_question_text(obs)).lower()
    if "any other" in blob:
        return "Batch, Pat the Baker, SuperValu"
    if "brand" in blob and "bread" in blob:
        stored = str((obs.kb or {}).get("bread_brands_aware") or "").strip()
        return stored.replace("&", " and ").replace("'", "") or (
            "Brennans, Johnston Mooney and OBrien"
        )
    if "role model" in blob:
        return "I look up to people who stay calm and help others succeed."
    sentence = "I usually buy what is cheap and easy to find locally."
    while open_text_word_count(sentence) < max(5, minimum):
        sentence += " It works for me."
    return sentence


def open_text_needs_more_words(obs: Observation) -> bool:
    if not open_text_question_visible(obs.ocr_text):
        return False
    need = min_words_required(obs.ocr_text)
    current = open_text_current_value(obs)
    if re.search(r"(?i)\btype your answer", current) or not current.strip():
        return True
    if current.lower() in current_question_text(obs).lower():
        return True
    if open_text_box_has_answer(obs):
        return False
    if _OPEN_TEXT_DONE.get(open_text_screen_key(obs)) or _OPEN_TEXT_TYPED.get(open_text_screen_key(obs)):
        return False
    if re.search(r"\d{3,}$", current.replace(" ", "")):
        return True
    if re.match(r"(?i)^[A-Z]?W[A-Z][a-z]", current):
        return True
    return open_text_word_count(current) < need


def open_text_answer_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Type a real sentence of at least N words, then Continue. No VLM required."""
    if not open_text_question_visible(obs.ocr_text):
        return None
    key = open_text_screen_key(obs)
    if _OPEN_TEXT_DONE.get(key) or open_text_box_has_answer(obs) or _OPEN_TEXT_TYPED.get(key):
        logger.info("[OPEN TEXT] Box already has an answer; Continue once and leave this screen.")
        return survey_next_decision(obs)
    need = min_words_required(obs.ocr_text)
    if open_text_needs_more_words(obs) or not _OPEN_TEXT_TYPED.get(key):
        payload = open_text_sentence(obs, need)
        coords = text_entry_field_coords(obs)
        logger.info("[OPEN TEXT] Typing %s-word answer (%s words required) payload=%r",
                    open_text_word_count(payload), need, payload)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"The box requires at least {need} words. Type a complete sentence.",
            "action": "type_text",
            "target_element_id": None,
            "target_text": "comment box",
            "target_coords": coords,
            "input_payload": payload,
            "kb_key": "open_text_comment",
            "kb_write": False,
            "missing_fact_key": None,
            "confidence_score": 0.92,
            "postcondition": f"field contains at least {need} words",
            "visual_reasoning": "The hint says at least 5 words; a three-word list is not enough.",
            "answer_provenance": "inferred",
            "source_basis": "Visible min-word validation + question text",
            "inference_confidence": 0.88,
        }
    logger.info("[OPEN TEXT] Word count met; grounding Next/Continue (keyboard may stay up).")
    return survey_next_decision(obs)


def configured_text_answer_decision(
    obs: Observation, stagnation_count: int = 0,
) -> Optional[dict[str, Any]]:
    """Fill known scalar KB facts into visible WebView text-entry questions."""
    if obs.screen_phase != "survey_question":
        return None
    question = re.sub(r"\s+", " ", obs.ocr_text.lower())
    kb_key = resolve_text_kb_key(obs.ocr_text) or resolve_text_kb_key(current_question_text(obs))
    if not kb_key:
        return None
    value = kb_or_persona_value(obs, kb_key)
    if value in (None, ""):
        return None
    payload = str(value).strip()
    if kb_key != "child_age" and re.search(rf"\b{re.escape(payload.lower())}\b", question) and "enter" not in question:
        return survey_next_decision(obs)
    # Age/name questions include the word in the prompt; do not treat that as already typed.
    if kb_key != "age" and re.search(rf"\b{re.escape(payload.lower())}\b", question):
        # Still type if the field looks empty and the payload is not just a prompt word.
        pass
    target = editable_candidate(obs.ui_nodes, obs.ocr_text) or clickable_empty_field_node(obs)
    coords = None if (target and target.get("editable")) else text_entry_field_coords(obs, stagnation_count)
    logger.info(
        "[TEXT KB ROUTER] question matched kb_key=%s payload=%r node=%s coords=%s",
        kb_key, payload, target.get("id") if target else None, coords,
    )
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs) or obs.ocr_text,
        "answer_reason": f"Known text answer loaded from knowledge_base.json:{kb_key}.",
        "action": "type_text",
        "target_element_id": target.get("id") if target else None,
        "target_text": node_text(target) if target else f"{kb_key} input field",
        "target_coords": coords,
        "input_payload": payload,
        "kb_key": kb_key,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.99,
        "postcondition": f"field contains {payload}",
        "visual_reasoning": (
            "The visible prompt is asking for a stored personal fact; type the KB value "
            "into the empty field instead of asking the model again."
        ),
        "answer_provenance": "declared",
        "source_basis": f"knowledge_base.json:{kb_key}",
        "inference_confidence": 0.99,
    }


def repair_text_entry_decision(decision: dict[str, Any], obs: Observation) -> dict[str, Any]:
    """Fill missing type_text payloads and coerce bounding-box coordinates."""
    action = str(decision.get("action") or "").lower()
    if action not in {"type_text", "type_comment"}:
        return decision
    payload = decision.get("input_payload")
    target_text = str(decision.get("target_text") or "").strip()
    kb_key = str(decision.get("kb_key") or "").strip() or resolve_text_kb_key(
        str(decision.get("question_text") or "") + " " + obs.ocr_text
    )
    if payload in (None, "") and looks_like_typed_value(target_text):
        payload = target_text
        logger.info("[TEXT REPAIR] Copied input_payload from target_text=%r", target_text)
    if payload in (None, "") and kb_key:
        stored = kb_or_persona_value(obs, kb_key)
        if stored not in (None, ""):
            payload = str(stored).strip()
            logger.info("[TEXT REPAIR] Filled input_payload from KB %s=%r", kb_key, payload)
    if payload not in (None, ""):
        decision["input_payload"] = payload
        if kb_key:
            decision["kb_key"] = kb_key
    coords = coerce_tap_coords(
        decision.get("target_coords"),
        (obs.image_width, obs.image_height),
    )
    if coords is None and not node_by_id(obs.ui_nodes, decision.get("target_element_id")):
        coords = text_entry_field_coords(obs)
    if coords is not None:
        decision["target_coords"] = coords
    return decision


def is_personal_survey_question(obs: Observation) -> bool:
    key = observation_kb_key(obs)
    if key in PERSONAL_FACT_KEYS:
        return True
    if resolve_text_kb_key(obs.ocr_text) in PERSONAL_FACT_KEYS:
        return True
    question = current_question_text(obs).lower()
    return any(term in question for term in (
        "your age", "your name", "your gender", "your email", "pets",
        "marital", "children", "smoke", "employment", "live with you",
    ))



def editable_candidate(nodes: list[dict[str, Any]], question_text: str = "") -> Optional[dict[str, Any]]:
    editables = [n for n in nodes if n["editable"] and n["enabled"]]
    if not editables:
        return None

    # Prefer a reasonably sized lower/middle field, but never use a fixed coordinate.
    # If only one editable node exists, it is the strongest structured candidate.
    if len(editables) == 1:
        return editables[0]

    q = question_text.lower()
    for n in editables:
        combined = (n["text"] + " " + n["content_desc"]).lower()
        if any(term in q for term in ("postcode", "postal", "zip", "email", "name", "phone", "address")):
            if any(term in combined for term in ("postcode", "postal", "zip", "email", "name", "phone", "address")):
                return n
    return editables[0]


# ------------------------------------------------------------------------------
# Text input and atomic execution
