# 26_reason.py — screenshot-first SEE → THEREFORE, like a human looking at the phone.

_THINK_CACHE: dict[str, dict[str, Any]] = {}
_LOCAL_ADULT_AGE = adult_age_screen_decision


def mindset_prompt() -> str:
    """Operational traits, not slogans. Injected into every image-model ask."""
    return (
        "MINDSET: curiosity=what is on THIS screenshot; "
        "rationality=one action that advances the survey; "
        "open-mind=if last tap failed, try a different y or method; "
        "objectivity=pixels beat remembered coords; "
        "empiricism=unchanged screen means the tap missed; "
        "critical=is Continue/Participate actually visible; "
        "skepticism=use the detected navigation boundary, never a fixed y guess; "
        "honesty=if unknown, say so, do not fake a tap."
    )


def green_cta_milli(obs: Observation) -> list[list[int]]:
    """Centres of mapped green CTA controls, with a pixel-mask fallback."""
    if "build_screen_object_map" in globals():
        try:
            scene = build_screen_object_map(obs)
            mapped = [
                list(item.get("visual_milli") or item.get("milli") or [])
                for item in scene.get("controls", [])
                if item.get("role") == "button" and item.get("color") == "green"
                and len(item.get("visual_milli") or item.get("milli") or []) == 2
            ]
            if mapped:
                return mapped[:3]
        except Exception as exc:
            logger.debug("[COORD] Screen-map green lookup failed: %s", exc)
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return []
    try:
        image = cv2.imread(path)
        if image is None:
            return []
        height, width = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (35, 70, 50), (95, 255, 255))
        mask[: int(height * 0.62), :] = 0
        nav_top = safe_navigation_top_milli(obs) if "safe_navigation_top_milli" in globals() else 945
        mask[int(height * nav_top / 1000):, :] = 0
        row = (mask > 0).sum(axis=1)
        bars: list[list[int]] = []
        in_bar, start, need = False, 0, int(width * 0.40)
        for y, count in enumerate(row):
            if count >= need and not in_bar:
                in_bar, start = True, y
            elif count < need and in_bar:
                in_bar = False
                if y - start < int(height * 0.012):
                    continue
                mid = (start + y) // 2
                xs = [x for x in range(0, width, 4) if mask[mid, x] > 0]
                if xs:
                    bars.append([
                        int(((xs[0] + xs[-1]) // 2) * 1000 / width),
                        int(mid * 1000 / height),
                    ])
        if bars:
            logger.info("[COORD] green pill(s)=%s (tap the CENTER, not OCR baseline)", bars)
        return bars[:3]
    except Exception:
        return []


def critique_decision(obs: Observation, decision: dict[str, Any]) -> dict[str, Any]:
    """Apply the mindset to a planned tap before it hits the device."""
    if not decision:
        return decision
    if select_up_to_n_visible(obs.ocr_text):
        fill = select_up_to_n_decision(obs)
        if fill:
            logger.info("[MINDSET] rationality: select-up-to-N %s %r",
                        fill.get("action"), fill.get("target_text"))
            return fill
    if heard_of_assistants_visible(obs.ocr_text):
        fill = heard_of_assistants_decision(obs)
        if fill:
            logger.info("[MINDSET] curiosity: SEE intro/question, no choices → %s",
                        fill.get("action"))
            return fill
    if smartphone_brand_question_visible(obs.ocr_text):
        fill = smartphone_brand_decision(obs)
        if fill:
            logger.info("[MINDSET] empiricism: device brand → %r then purple arrow",
                        fill.get("target_text"))
            return fill
    if quoted_select_instruction_visible(obs.ocr_text):
        if str(decision.get("action") or "") == "select_then_continue":
            out = dict(decision)
            out.setdefault("mindset", "applied")
            logger.info("[MINDSET] rationality: keep radio-then-Continue for named option")
            return out
        fill = quoted_instruction_decision(obs)
        if fill:
            logger.info("[MINDSET] rationality: instruction names %r; tap radio then Continue",
                        fill.get("target_text"))
            return fill
    out = ground_decision_to_screen_map(dict(decision), obs) if "ground_decision_to_screen_map" in globals() else dict(decision)
    action = str(out.get("action") or "").lower()
    text = str(out.get("target_text") or "")
    tlow = text.lower()
    coords = out.get("target_coords")
    y = 0
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        try:
            y = int(coords[1])
        except (TypeError, ValueError):
            y = 0
    see = re.sub(r"\s+", " ", str(obs.ocr_text or ""))[:120]
    logger.info("[MINDSET] curiosity SEE=%r action=%s text=%r y=%s", see, action, text[:40], y)

    greens = green_cta_milli(obs)
    if any(tok in tlow for tok in ("participate", "get started", "start survey")):
        if greens:
            gx, gy = int(greens[-1][0]), int(greens[-1][1])
            out["target_coords"] = [gx, gy]
            out["coordinate_authoritative"] = True
            logger.info("[MINDSET] objectivity: green-pill center [%s,%s] not OCR y=%s", gx, gy, y)
            y = gy
        elif y >= safe_navigation_top_milli(obs):
            out["target_coords"] = [500, max(700, safe_navigation_top_milli(obs) - 35)]
            out["coordinate_authoritative"] = True
            logger.info("[MINDSET] skepticism: Participate %s was below detected nav boundary", coords)
            y = int(out["target_coords"][1])

    nav_top = safe_navigation_top_milli(obs) if "safe_navigation_top_milli" in globals() else 945
    if y >= nav_top and action in {"click", "select_option"}:
        logger.info("[MINDSET] skepticism: y=%s is at/below detected Android nav=%s", y, nav_top)
        out["target_coords"] = [500, max(700, nav_top - 35)]
        out["coordinate_authoritative"] = True

    failed = failed_coords_set() if "failed_coords_set" in globals() else set()
    if isinstance(out.get("target_coords"), list) and len(out["target_coords"]) == 2:
        pair = (int(out["target_coords"][0]), int(out["target_coords"][1]))
        if pair in failed and not out.get("object_map_grounded"):
            alt_y = max(120, min(nav_top - 20, pair[1] + 24))
            out["target_coords"] = [pair[0], alt_y]
            out["answer_reason"] = (
                f"EMPIRICISM/open-mind: {pair} already missed; trying y={alt_y}."
            )
            logger.info("[MINDSET] empiricism: %s failed; retry y=%s", pair, alt_y)

    if qualified_landing_visible(obs.ocr_text) and "participate" not in tlow and action == "click":
        fill = navigation_cta_decision(obs)
        if fill and "participate" in str(fill.get("target_text") or "").lower():
            logger.info("[MINDSET] rationality: landing shows Participate; using that CTA")
            return fill

    if action in {"select_option", "click"} and not out.get("input_payload") and looks_like_single_choice(obs.ocr_text):
        if is_progression_cta(text):
            logger.info("[MINDSET] honesty: Continue with empty payload on a radio page; fill first")
            fill = single_choice_radio_decision(obs) if "single_choice_radio_decision" in globals() else None
            if fill:
                return fill

    out.setdefault("mindset", "applied")
    return out


def mindset_regression_self_check() -> bool:
    ocr = (
        "You've qualified for this survey! Click below to get started. "
        "Survey will take around 38 minutes. Participate"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="mindset-part",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={},
        screen_phase="survey_landing", survey_tiles=[],
    )
    raw = {
        "action": "click", "target_text": "Participate",
        "target_coords": [499, 899], "confidence_score": 0.95,
    }
    fixed = critique_decision(obs, raw)
    y = int((fixed.get("target_coords") or [0, 0])[1])
    prompt = mindset_prompt()
    passed = (
        "skepticism" in prompt and "empiricism" in prompt
        and "curiosity" in prompt and "honesty" in prompt
        and 890 <= y <= 910
        and "participate" in str(fixed.get("target_text") or "").lower()
    )
    if passed:
        logger.info("[SELF-CHECK] Mindset keeps the detected Participate centre y=%s.", y)
    else:
        logger.error("[SELF-CHECK] Mindset failed y=%s decision=%s", y, fixed)
    return passed


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
        f"{mindset_prompt()}\n"
        "LOOK at this Android survey screenshot.\n"
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
        logger.info("[THINK] SEE box=%s typed=%s THEREFORE purple arrow",
                    digits or wanted, _AGE_SESSION.get("typed"))
        coords = adult_age_continue_coords(obs)
        return {
            **local,
            "action": "click", "target_text": "arrow", "target_coords": coords,
            "coordinate_authoritative": True, "input_payload": None, "kb_key": "age",
            "answer_reason": "SEE age entered. THEREFORE tap the purple arrow; do not retype.",
            "dismiss_keyboard": False, "skip_object_grounding": True, "object_kind": "button",
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
            **local, "action": "click", "target_text": "arrow",
            "target_coords": coords or adult_age_continue_coords(obs),
            "coordinate_authoritative": True, "kb_key": "age",
            "answer_reason": f"VLM SEE {thought.get('see')}. THEREFORE purple arrow.",
            "dismiss_keyboard": False, "skip_object_grounding": True,
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
