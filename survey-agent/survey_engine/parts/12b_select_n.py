# 12b_select_n.py — select-up-to-N multi-choice (grid coords, then footer arrow)

_SELECT_N_SESSION: dict[str, Any] = {"key": "", "ticked": [], "picks": []}
_LLM_PICK_CACHE: dict[str, list[str]] = {}
SELECT_N_PREFERRED = (
    "Productivity at work", "Reducing repetitive tasks", "Finding information faster",
    "Creativity and content creation", "Learning and education",
)
SELECT_N_ORDER = (
    "Reducing repetitive tasks", "Accessibility for people with disabilities",
    "Learning and education", "Productivity at work", "Translation and communication",
    "Finding information faster", "Creativity and content creation",
)


def is_garbage_option_label(text: str) -> bool:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(raw) < 4 or re.search(r"\d{1,2}:\d{2}", raw) or re.search(r"\d{1,3}%", raw):
        return True
    if len(re.sub(r"[^A-Za-z]", "", raw)) < 4:
        return True
    return raw.lower() in {"survey", "continue", "next", "select up to 3", "select up to"}


def clean_option_label(text: str) -> str:
    line = re.sub(r"^[\s\(\)\[\]\.C|]+", "", str(text or "")).strip()
    line = re.sub(r"^[A-Z]{1,3}\s+(?=[A-Za-z])", "", line)
    return re.sub(r"\s+", " ", line)


def select_up_to_n_visible(ocr_text: str) -> bool:
    return bool(re.search(r"select up to\s+\d+", re.sub(r"\s+", " ", str(ocr_text or "").lower())))


def select_up_to_limit(ocr_text: str) -> int:
    match = re.search(r"select up to\s+(\d+)", str(ocr_text or "").lower())
    return max(1, min(5, int(match.group(1)))) if match else 3


def select_n_session_key(obs: Observation) -> str:
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if "excites you most" in text:
        return "excites-ai-assistants"
    return "select-n:" + question_fingerprint(obs)[:20]


def select_up_to_labels(obs: Observation) -> list[str]:
    found: list[str] = []
    for raw in str(obs.ocr_text or "").splitlines():
        line = clean_option_label(raw)
        if is_garbage_option_label(line) or is_chrome_option_label(line):
            continue
        if "?" in line or line.lower().startswith("in general") or len(line) > 80:
            continue
        if line.lower() not in {x.lower() for x in found}:
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
    key = select_n_session_key(obs)
    if key in _LLM_PICK_CACHE:
        cached = [p for p in _LLM_PICK_CACHE[key] if any(p.lower()[:12] in lab.lower() for lab in labels)]
        if cached:
            return cached[:need]
    if obs.screenshot and labels and "call_vlm" in globals() and key not in _LLM_PICK_CACHE:
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


def footer_cta_milli(obs: Observation) -> list[int]:
    """Object-map / purple contour of the bottom arrow only (y>=800). Never a mid-list row."""
    try:
        scene = build_screen_object_map(obs)
        best = None
        for item in scene.get("controls") or []:
            milli = list(item.get("visual_milli") or item.get("milli") or [])
            if len(milli) != 2:
                continue
            x, y = int(milli[0]), int(milli[1])
            if y < 800 or y > 940 or abs(x - 500) > 220:
                continue
            if best is None or y > best[1]:
                best = [x, y]
        if best:
            logger.info("[SELECT N] Grid footer CTA %s", best)
            return best
    except Exception:
        pass
    purple = purple_submit_arrow_milli(obs) if "purple_submit_arrow_milli" in globals() else None
    if purple and 800 <= int(purple[1]) <= 940:
        return [int(purple[0]), int(purple[1])]
    return [500, 875]


def select_n_grid_milli(obs: Observation, pick: str) -> list[int]:
    """Left checkbox of the named row from the object grid, else known layout."""
    mapped = mapped_option_milli(obs, pick) if "mapped_option_milli" in globals() else None
    if mapped and 250 <= int(mapped[1]) <= 790:
        logger.info("[SELECT N] Grid option %r %s", pick, mapped)
        return [180, int(mapped[1])]
    low = clean_option_label(pick).lower()
    for index, name in enumerate(SELECT_N_ORDER):
        if name.lower()[:14] in low or low[:14] in name.lower():
            return [180, 343 + index * 67]
    return [180, 430]


def select_n_already_checked(obs: Observation, pick: str) -> bool:
    needle = clean_option_label(pick).lower()[:14]
    for node in obs.ui_nodes or []:
        if not (node.get("checked") or node.get("selected")):
            continue
        blob = (str(node.get("text") or "") + " " + str(node.get("content_desc") or "")).lower()
        if needle in blob:
            return True
    return False


def select_up_to_n_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tick remaining real options on the grid, then the footer purple arrow."""
    if not select_up_to_n_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    need = select_up_to_limit(obs.ocr_text)
    labels = [clean_option_label(x) for x in select_up_to_labels(obs)]
    key = select_n_session_key(obs)
    if _SELECT_N_SESSION.get("key") != key:
        _SELECT_N_SESSION.update({"key": key, "ticked": [], "picks": select_up_to_rank(obs, labels, need)})
    picks = [clean_option_label(p) for p in (_SELECT_N_SESSION.get("picks") or [])] or select_up_to_rank(obs, labels, need)
    _SELECT_N_SESSION["picks"] = picks
    ticked = [clean_option_label(t) for t in (_SELECT_N_SESSION.get("ticked") or [])]
    for pick in picks:
        if select_n_already_checked(obs, pick) and pick not in ticked:
            ticked.append(pick)
    _SELECT_N_SESSION["ticked"] = ticked
    remaining = [p for p in picks if p.lower() not in {t.lower() for t in ticked}]
    if remaining and labels and len(ticked) < need:
        pick = remaining[0]
        tap = select_n_grid_milli(obs, pick)
        _SELECT_N_SESSION["ticked"] = ticked + [pick]
        logger.info("[SELECT N] %s/%s tick %r grid=%s", len(ticked) + 1, need, pick, tap)
        return {
            "screen_state": "survey_question", "action": "select_option",
            "target_text": pick, "target_coords": tap, "coordinate_authoritative": True,
            "input_payload": pick, "kb_key": "ai_assistant_excitement", "kb_write": False,
            "confidence_score": 0.95, "postcondition": "selected option is " + pick,
            "answer_reason": f"Select up to {need}: tick {pick} on the grid, then the footer arrow.",
            "skip_object_grounding": True,
        }
    arrow = footer_cta_milli(obs)
    logger.info("[SELECT N] ticked %s; footer arrow %s", ticked, arrow)
    return {
        "screen_state": "survey_question", "action": "click", "target_text": "Continue",
        "target_coords": arrow, "coordinate_authoritative": True,
        "input_payload": ", ".join(ticked), "kb_key": "ai_assistant_excitement", "kb_write": True,
        "confidence_score": 0.96, "postcondition": "screen changed",
        "answer_reason": f"Selected {ticked}; tap the footer purple arrow at {arrow}.",
        "skip_object_grounding": True, "object_kind": "button",
    }


def select_up_to_n_regression_self_check() -> bool:
    """Select-up-to-3 uses grid rows then a footer arrow (y>=800), never YW/header/y=705."""
    ocr = (
        "In general, what excites you most about AI assistants?\nSelect up to 3\n"
        "YW Reducing repetitive tasks\nAccessibility for people with disabilities\n"
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
    noisy = Observation(**{**obs.__dict__, "ocr_text": ocr + "\n3:31 banner"})
    arrow = select_up_to_n_decision(noisy)
    exact = exact_kb_option_decision(obs)
    labels = select_up_to_labels(obs)
    passed = bool(
        select_up_to_n_visible(ocr) and select_up_to_limit(ocr) == 3
        and is_garbage_option_label("ee")
        and "YW Reducing repetitive tasks" not in labels
        and any("Reducing repetitive" in x for x in labels)
        and first and first.get("action") == "select_option" and "YW" not in str(first.get("target_text"))
        and int((first.get("target_coords") or [0, 0])[1]) < 800
        and second and second.get("target_text") != first.get("target_text")
        and third and third.get("action") == "select_option"
        and arrow and arrow.get("action") == "click"
        and int((arrow.get("target_coords") or [0, 0])[1]) >= 800
        and arrow.get("skip_object_grounding")
        and (exact is None or str(exact.get("target_text") or "") != "ee")
    )
    if passed:
        logger.info("[SELF-CHECK] Select-up-to-3 ticks grid rows then footer arrow y>=800.")
    else:
        logger.error("[SELF-CHECK] Select-N failed first=%s second=%s third=%s arrow=%s labels=%s",
                     first, second, third, arrow, labels)
    return passed
