# 12b_select_n.py — select-up-to-N multi-choice (LLM/persona then purple arrow)

_SELECT_N_SESSION: dict[str, Any] = {"key": "", "ticked": [], "picks": []}
_LLM_PICK_CACHE: dict[str, list[str]] = {}
SELECT_N_PREFERRED = (
    "Productivity at work", "Reducing repetitive tasks", "Finding information faster",
    "Creativity and content creation", "Learning and education",
)


def is_garbage_option_label(text: str) -> bool:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(raw) < 4:
        return True
    if re.search(r"\d{1,2}:\d{2}", raw) or re.search(r"\d{1,3}%", raw):
        return True
    letters = re.sub(r"[^A-Za-z]", "", raw)
    if len(letters) < 4:
        return True
    low = raw.lower()
    return low in {"survey", "continue", "next", "select up to 3", "select up to"}


def select_up_to_n_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return bool(re.search(r"select up to\s+\d+", text))


def select_up_to_limit(ocr_text: str) -> int:
    match = re.search(r"select up to\s+(\d+)", str(ocr_text or "").lower())
    return max(1, min(5, int(match.group(1)))) if match else 3


def select_up_to_labels(obs: Observation) -> list[str]:
    found: list[str] = []
    for raw in str(obs.ocr_text or "").splitlines():
        line = re.sub(r"^[\s\(\)\[\]\.C|]+", "", raw).strip()
        line = re.sub(r"\s+", " ", line)
        if is_garbage_option_label(line) or is_chrome_option_label(line):
            continue
        if "?" in line or line.lower().startswith("in general"):
            continue
        if line.lower() in {x.lower() for x in found} or len(line) > 80:
            continue
        found.append(line)
    return found[:12]


def select_up_to_rank(obs: Observation, labels: list[str], need: int) -> list[str]:
    ranked = [lab for pref in SELECT_N_PREFERRED for lab in labels if pref.lower()[:18] in lab.lower()]
    local: list[str] = []
    for lab in ranked + labels:
        if lab not in local and not is_garbage_option_label(lab):
            local.append(lab)
        if len(local) >= need:
            break
    key = question_fingerprint(obs)
    if key in _LLM_PICK_CACHE:
        cached = [p for p in _LLM_PICK_CACHE[key] if any(p.lower()[:12] in lab.lower() for lab in labels)]
        if cached:
            return cached[:need]
    if obs.screenshot and labels and "call_vlm" in globals():
        prompt = (
            f"ASK: tick at most {need} boxes a 44-year-old Lead Data Scientist would choose.\n"
            "CHOICES:\n" + "\n".join(f"- {x}" for x in labels) +
            '\nReturn JSON only: {"picks":["exact label from CHOICES",...]}'
        )
        try:
            raw, _backend = call_vlm(prompt, Path(obs.screenshot), prompt, prefer_flash=False)
            data = parse_json_response(raw) if "parse_json_response" in globals() else {}
            mapped: list[str] = []
            for pick in data.get("picks") or []:
                if not isinstance(pick, str):
                    continue
                hit = next((lab for lab in labels if pick.lower()[:16] in lab.lower() or lab.lower()[:16] in pick.lower()), None)
                if hit and hit not in mapped:
                    mapped.append(hit)
            if mapped:
                _LLM_PICK_CACHE[key] = mapped[:need]
                logger.info("[SELECT N] LLM picks=%s", mapped[:need])
                return mapped[:need]
        except Exception as exc:
            logger.info("[SELECT N] LLM rank skipped: %s", exc)
    return local[:need]


def select_up_to_n_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tick up to N real options (LLM/persona), then the purple arrow. Never 'ee'."""
    if not select_up_to_n_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    need = select_up_to_limit(obs.ocr_text)
    labels = select_up_to_labels(obs)
    key = question_fingerprint(obs)
    if _SELECT_N_SESSION.get("key") != key:
        _SELECT_N_SESSION.update({"key": key, "ticked": [], "picks": select_up_to_rank(obs, labels, need)})
    picks = list(_SELECT_N_SESSION.get("picks") or []) or select_up_to_rank(obs, labels, need)
    _SELECT_N_SESSION["picks"] = picks
    ticked = list(_SELECT_N_SESSION.get("ticked") or [])
    arrow = heard_of_arrow_milli(obs) if "heard_of_arrow_milli" in globals() else [500, 860]
    remaining = [p for p in picks if p.lower() not in {t.lower() for t in ticked}]
    if remaining and labels:
        pick = remaining[0]
        row = select_one_ocr_row_milli(obs, pick) if "select_one_ocr_row_milli" in globals() else None
        tap = [int(row[0]), int(row[1])] if row else [180, 360 + min(len(ticked), 6) * 70]
        _SELECT_N_SESSION["ticked"] = ticked + [pick]
        logger.info("[SELECT N] %s/%s tick %r at %s", len(ticked) + 1, need, pick, tap)
        return {
            "screen_state": "survey_question", "action": "select_option",
            "target_text": pick, "target_coords": tap, "coordinate_authoritative": True,
            "input_payload": pick, "kb_key": "ai_assistant_excitement", "kb_write": True,
            "confidence_score": 0.95, "postcondition": "selected option is " + pick,
            "answer_reason": f"Select up to {need}: tick {pick}, then the purple arrow.",
        }
    logger.info("[SELECT N] ticked %s; purple arrow %s", ticked, arrow)
    return {
        "screen_state": "survey_question", "action": "click", "target_text": "Continue",
        "target_coords": arrow, "coordinate_authoritative": True,
        "input_payload": ", ".join(ticked), "kb_key": "ai_assistant_excitement", "kb_write": True,
        "confidence_score": 0.96, "postcondition": "screen changed",
        "answer_reason": f"Selected {ticked}; tap the purple arrow.",
        "skip_object_grounding": True, "object_kind": "button",
    }


def select_up_to_n_regression_self_check() -> bool:
    """Select-up-to-3 ticks real options then the purple arrow, never OCR junk 'ee'."""
    ocr = (
        "In general, what excites you most about AI assistants?\nSelect up to 3\n"
        "Reducing repetitive tasks\nAccessibility for people with disabilities\n"
        "Learning and education\nProductivity at work\nTranslation and communication\n"
        "Finding information faster\nCreativity and content creation (including images)\nee"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="select-n",
        ocr_text=ocr, ui_nodes=[], kb={"education": "Master's Degree"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _SELECT_N_SESSION.update({"key": "", "ticked": [], "picks": []})
    first = select_up_to_n_decision(obs)
    second = select_up_to_n_decision(obs)
    third = select_up_to_n_decision(obs)
    arrow = select_up_to_n_decision(obs)
    exact = exact_kb_option_decision(obs)
    passed = bool(
        select_up_to_n_visible(ocr) and select_up_to_limit(ocr) == 3
        and is_garbage_option_label("ee")
        and first and first.get("action") == "select_option" and first.get("target_text") != "ee"
        and len(str(first.get("target_text") or "")) > 8
        and second and second.get("target_text") not in {"ee", first.get("target_text")}
        and third and third.get("action") == "select_option"
        and arrow and arrow.get("action") == "click"
        and int((arrow.get("target_coords") or [0, 0])[1]) >= 500
        and (exact is None or str(exact.get("target_text") or "") != "ee")
    )
    if passed:
        logger.info("[SELF-CHECK] Select-up-to-3 ticks real options then the purple arrow.")
    else:
        logger.error("[SELF-CHECK] Select-N failed first=%s second=%s third=%s arrow=%s exact=%s",
                     first, second, third, arrow, exact)
    return passed
