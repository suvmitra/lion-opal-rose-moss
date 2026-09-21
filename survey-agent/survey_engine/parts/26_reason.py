# 26_reason.py — screenshot-first SEE → THEREFORE, like a human looking at the phone.

_THINK_CACHE: dict[str, dict[str, Any]] = {}
_LOCAL_ADULT_AGE = adult_age_screen_decision


def think_from_screenshot(obs: Observation, fact: str) -> dict[str, Any]:
    """Ask the image model what is actually on screen before we tap."""
    path = Path(str(obs.screenshot or ""))
    key = f"{getattr(obs, 'screen_hash', '')}:{fact[:60]}"
    if key in _THINK_CACHE:
        return _THINK_CACHE[key]
    if not path.exists():
        return {}
    if not gemini_configured() and not (salad_configured() and _SALAD_ONLINE):
        logger.warning("[THINK] No image model; using local OCR only.")
        return {}
    prompt = (
        "LOOK at this Android survey screenshot. Think like a careful, curious, honest human.\n"
        "Use: curiosity (what is actually on screen?), rationality (what must happen to go next?),\n"
        "objectivity (trust pixels over old coords), empiricism (did the last tap move the screen?),\n"
        "skepticism (is this the Android nav bar or the real button?), intellectual honesty.\n"
        f"FACT: {fact}\n"
        "SEE: quote the question, the EXACT characters in the input box, "
        "any red error, and whether an orange Continue bar is visible.\n"
        "THEREFORE: one next action. If the box is 4444 or >99, CLEAR it and type 44. "
        "Do not tap Continue until the box is exactly 44.\n"
        "JSON only: "
        '{"see":"box=... error=...","therefore":"...","action":"type_text|click",'
        '"input_payload":"44","target_text":"age input field","target_coords":[500,380]}'
    )
    compact = (
        '{"see":"box=4444 error=no more than 99","therefore":"replace with 44",'
        '"action":"type_text","input_payload":"44","target_text":"age input field",'
        '"target_coords":[500,380]}'
    )
    try:
        raw, backend = call_vlm(prompt, path, compact, prefer_flash=True)
        data = parse_json_response(raw)
        logger.info(
            "[THINK] backend=%s see=%s therefore=%s action=%s",
            backend, data.get("see"), data.get("therefore"), data.get("action"),
        )
        _THINK_CACHE[key] = data
        return data
    except Exception as exc:
        logger.warning("[THINK] VLM failed: %s", exc)
        return {}


def _digits_in_thought(thought: dict[str, Any]) -> str:
    blob = " ".join(str(thought.get(key) or "") for key in ("see", "therefore", "input_payload"))
    fours = re.findall(r"4{2,6}", blob)
    if fours:
        return max(fours, key=len)
    found = re.findall(r"(?<!\d)(\d{1,3})(?!\d)", blob)
    if "44" in found:
        return "44"
    return found[0] if found else ""


def adult_age_screen_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """SEE the box, THEN act. VLM is asked when OCR did not read the number."""
    local = _LOCAL_ADULT_AGE(obs)
    if local is None:
        return None
    wanted = adult_age_payload(obs)
    digits = adult_age_visible_digits(obs)
    too_big = bool(re.search(r"4{3,6}", str(digits or "")))
    if (digits == wanted or _AGE_SESSION.get("typed")) and not too_big:
        logger.info("[THINK] SEE box=%s typed=%s THEREFORE Continue",
                    digits or wanted, _AGE_SESSION.get("typed"))
        coords = adult_age_continue_coords(obs)
        return {
            **local,
            "action": "click", "target_text": "Continue", "target_coords": coords,
            "coordinate_authoritative": True, "input_payload": None, "kb_key": "age",
            "answer_reason": f"SEE 44 in the box. THEREFORE hide keyboard and tap Continue.",
            "dismiss_keyboard": True,
        }
    if local.get("action") == "type_text" and str(local.get("input_payload")) == wanted:
        logger.info("[THINK] SEE box=%r THEREFORE type %s (local)", digits or "empty/wrong", wanted)
        return local
    thought = think_from_screenshot(
        obs,
        f"knowledge_base age={wanted}. Read the rounded text box. "
        "If it is 4444 or over 99, replace with 44, then Continue.",
    )
    seen = _digits_in_thought(thought) or digits
    logger.info("[THINK] SEE local=%r vlm=%r wanted=%s", digits, seen, wanted)
    if seen == wanted and thought.get("action") == "click":
        coords = thought.get("target_coords") if isinstance(thought.get("target_coords"), list) else adult_age_continue_coords(obs)
        return {
            **local, "action": "click", "target_text": "Continue",
            "target_coords": coords or adult_age_continue_coords(obs),
            "coordinate_authoritative": True, "kb_key": "age",
            "answer_reason": f"VLM SEE {thought.get('see')}. THEREFORE Continue.",
        }
    coords = adult_age_field_coords(obs)
    if isinstance(thought.get("target_coords"), list) and thought.get("action") == "type_text":
        coords = thought["target_coords"]
    return {
        "screen_state": "survey_question", "action": "type_text",
        "target_text": "age input field", "target_coords": coords,
        "coordinate_authoritative": True, "input_payload": wanted, "kb_key": "age",
        "confidence_score": 0.99, "postcondition": f"field contains {wanted}",
        "answer_reason": (
            f"SEE box={seen or 'unread'}. THEREFORE replace with {wanted}. "
            f"{thought.get('therefore') or ''}"
        ).strip(),
    }
