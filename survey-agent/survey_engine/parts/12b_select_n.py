# 12b_select_n.py — select-up-to-N multi-choice (grid coords, then footer arrow)

_SELECT_N_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_SELECT_N_SESSION: dict[str, Any] = {"key": "", "ticked": [], "picks": []}
_LLM_PICK_CACHE: dict[str, list[str]] = {}
SELECT_N_PREFERRED = (
    "Helping to complete a task", "Summarising emails", "Finding photos",
    "Productivity at work", "Reducing repetitive tasks", "Finding information faster",
    "Creativity and content creation", "Learning and education",
    "Translating conversations", "Managing calendar",
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
    return "question is required" in raw.lower() or raw.lower() in {
        "survey", "continue", "next", "select up to 3", "select up to",
    }


def clean_option_label(text: str) -> str:
    line = re.sub(r"^[\s\(\)\[\]\.C|]+", "", str(text or "")).strip()
    line = re.sub(r"^[A-Z]{1,3}\s+(?=[A-Za-z])", "", line)
    return re.sub(r"\s+", " ", line)


def select_up_to_n_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return bool(re.search(r"select up to\s+(\d+|one|two|three|four|five)", text))


def select_up_to_limit(ocr_text: str) -> int:
    match = re.search(r"select up to\s+(\d+|one|two|three|four|five)", str(ocr_text or "").lower())
    if not match:
        return 3
    token = match.group(1)
    return max(1, min(5, _SELECT_N_WORDS.get(token, int(token) if token.isdigit() else 3)))


def select_n_session_key(obs: Observation) -> str:
    text = re.sub(r"this question is required", " ", re.sub(r"\s+", " ", str(obs.ocr_text or "").lower()))
    words = [w for w in re.findall(r"[a-z]{4,}", text) if w not in {
        "survey", "please", "select", "which", "following", "would", "three", "this",
    }]
    return "select-n:" + " ".join(words[:6])


def select_up_to_labels(obs: Observation) -> list[str]:
    found: list[str] = []
    for raw in str(obs.ocr_text or "").splitlines():
        line = clean_option_label(raw)
        if is_garbage_option_label(line) or is_chrome_option_label(line):
            continue
        if "?" in line or line.lower().startswith("in general") or len(line) > 80:
            continue
        if "required" in line.lower() or is_banner_or_instruction_label(line):
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
    """Centre of the filled purple footer pill. Never a left-edge fragment (x=326)."""
    y = 890
    try:
        scene = build_screen_object_map(obs)
        for item in scene.get("controls") or []:
            milli = list(item.get("visual_milli") or item.get("milli") or [])
            if len(milli) != 2:
                continue
            cy = int(milli[1])
            if 820 <= cy <= 940:
                y = max(y, cy) if y != 890 else cy
    except Exception:
        pass
    purple = purple_submit_arrow_milli(obs) if "purple_submit_arrow_milli" in globals() else None
    if purple and 820 <= int(purple[1]) <= 940:
        y = int(purple[1])
    logger.info("[SELECT N] Grid footer CTA [%s, %s]", 500, y)
    return [500, y]


def select_n_map_checkbox_milli(obs: Observation, pick: str) -> Optional[list[int]]:
    """Left checkbox of the mapped card for this label (screen-object grid)."""
    if "build_screen_object_map" not in globals():
        return None
    try:
        scene = build_screen_object_map(obs)
    except Exception:
        return None
    needle = clean_option_label(pick).lower()[:14]
    width = max(1, int(obs.image_width or 1440))
    height = max(1, int(obs.image_height or 3088))
    cards: list[tuple[int, list[int]]] = []
    for item in scene.get("controls") or []:
        label = str(item.get("label") or "").lower()
        if needle[:10] not in label and label[:10] not in needle:
            continue
        bounds = list(item.get("visual_bounds") or item.get("bounds") or [])
        if len(bounds) != 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in bounds]
        if y2 < height * 0.28 or y1 > height * 0.82:
            continue
        cards.append((x2 - x1, [x1, y1, x2, y2]))
    if not cards:
        return None
    x1, y1, x2, y2 = max(cards, key=lambda row: row[0])[1]
    cx = int(((x1 + min(64, max(28, (x2 - x1) * 0.08))) / width) * 1000)
    cy = int((((y1 + y2) / 2) / height) * 1000)
    best = [max(90, min(220, cx)), max(300, min(800, cy))]
    logger.info("[SELECT N] Map checkbox %r %s bounds=%s", pick, best, [x1, y1, x2, y2])
    return best


def select_n_grid_milli(obs: Observation, pick: str, labels: Optional[list[str]] = None) -> list[int]:
    mapped = select_n_map_checkbox_milli(obs, pick)
    if mapped:
        return mapped
    low = clean_option_label(pick).lower()
    sequence = list(labels or []) or list(SELECT_N_ORDER)
    for index, name in enumerate(sequence):
        if name.lower()[:14] in low or low[:14] in name.lower():
            return [140, 445 + index * 78]
    return [140, 445]


def select_n_required_banner(obs: Observation) -> bool:
    return "question is required" in re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())


def select_n_already_checked(obs: Observation, pick: str) -> bool:
    needle = clean_option_label(pick).lower()[:14]
    for node in obs.ui_nodes or []:
        if not (node.get("checked") or node.get("selected")):
            continue
        blob = (str(node.get("text") or "") + " " + str(node.get("content_desc") or "")).lower()
        if needle in blob:
            return True
    return False


def select_n_visually_checked(obs: Observation, labels: list[str]) -> list[str]:
    """Gray filled cards from the object-map bounds. Empty white cards are not checked."""
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists() or not labels:
        return []
    try:
        image = cv2.imread(path)
        scene = build_screen_object_map(obs) if "build_screen_object_map" in globals() else {}
        if image is None:
            return []
        found: list[str] = []
        for lab in labels:
            needle = lab.lower()[:12]
            for item in scene.get("controls") or []:
                if needle not in str(item.get("label") or "").lower():
                    continue
                bounds = list(item.get("visual_bounds") or item.get("bounds") or [])
                if len(bounds) != 4:
                    continue
                x1, y1, x2, y2 = [int(v) for v in bounds]
                crop = image[y1 + 6: max(y1 + 7, y2 - 6), x1 + 50: min(x2 - 8, x1 + 420)]
                if crop.size == 0:
                    continue
                mean = float(crop.mean())
                if 140.0 < mean < 222.0 and lab not in found:
                    found.append(lab)
                    logger.info("[SELECT N] Gray card %r mean=%.1f", lab, mean)
        return found
    except Exception:
        return []


def select_up_to_n_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """6-step workflow: SEE → ASK → GRID → ACT → VALIDATE → ARROW."""
    if not select_up_to_n_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    need = select_up_to_limit(obs.ocr_text)
    labels = [clean_option_label(x) for x in select_up_to_labels(obs)]
    key = select_n_session_key(obs)
    if _SELECT_N_SESSION.get("key") != key:
        _SELECT_N_SESSION.update({"key": key, "ticked": [], "picks": [], "miss": 0, "attempted": []})
    picks = [clean_option_label(p) for p in (_SELECT_N_SESSION.get("picks") or [])] or select_up_to_rank(obs, labels, need)
    _SELECT_N_SESSION["picks"] = picks
    banner = select_n_required_banner(obs)
    visual = select_n_visually_checked(obs, labels)
    if obs.screenshot:
        ticked = [p for p in picks if select_n_already_checked(obs, p) or any(p.lower()[:12] in v.lower() for v in visual)]
    else:
        ticked = [clean_option_label(t) for t in (_SELECT_N_SESSION.get("attempted") or [])]
    _SELECT_N_SESSION["ticked"] = ticked
    remaining = [p for p in picks if p.lower() not in {t.lower() for t in ticked}]
    logger.info(
        "[SELECT N WORKFLOW] 1 SEE banner=%s visual=%s 2 ASK picks=%s 5 VALIDATE ticked=%s",
        banner, visual, picks, ticked,
    )
    must_tick = bool(remaining and len(ticked) < need) or bool(banner and obs.screenshot and len(ticked) < need)
    if must_tick and labels and picks:
        pick = remaining[0] if remaining else picks[int(_SELECT_N_SESSION.get("miss") or 0) % len(picks)]
        tap = select_n_grid_milli(obs, pick, labels)
        _SELECT_N_SESSION["attempted"] = list(_SELECT_N_SESSION.get("attempted") or []) + [pick]
        logger.info("[SELECT N WORKFLOW] 3 GRID %r -> %s  4 ACT tick", pick, tap)
        return {
            "screen_state": "survey_question", "action": "select_option",
            "target_text": pick, "target_coords": tap, "coordinate_authoritative": True,
            "input_payload": pick, "kb_key": "ai_assistant_valuable_features", "kb_write": False,
            "confidence_score": 0.95, "postcondition": "selected option is " + pick,
            "answer_reason": (
                f"SEE required={banner} checked={ticked}. ASK LLM/persona {picks}. "
                f"GRID tick {pick} at {tap}. Do not Continue while the banner is visible."
            ),
            "skip_object_grounding": True,
        }
    arrow = footer_cta_milli(obs)
    logger.info("[SELECT N WORKFLOW] 6 ARROW %s after %s", arrow, ticked)
    return {
        "screen_state": "survey_question", "action": "click", "target_text": "Continue",
        "target_coords": arrow, "coordinate_authoritative": True,
        "input_payload": ", ".join(ticked), "kb_key": "ai_assistant_valuable_features", "kb_write": True,
        "confidence_score": 0.96, "postcondition": "screen changed",
        "answer_reason": f"VALIDATE {need} boxes are selected and banner is gone; tap centred footer arrow {arrow}.",
        "skip_object_grounding": True, "object_kind": "button",
    }


def select_up_to_n_regression_self_check() -> bool:
    """Select-up-to-3 uses grid rows then a footer arrow (y>=800), never YW/header/y=705."""
    ocr = (
        "This question is required\n"
        "Which of the following features are, or would be, most valuable "
        "to you in an AI assistant on your phone?\nSelect up to three.\n"
        "Summarising emails or messages\n"
        "Helping to complete a task across multiple apps\n"
        "Finding photos, files, or notes\n"
        "Translating conversations or documents\n"
        "Managing calendar events\n"
        "Controlling phone settings"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="select-n",
        ocr_text=ocr, ui_nodes=[], kb={"education": "Master's Degree"}, persona={},
        screen_phase="survey_question", survey_tiles=[],
    )
    _SELECT_N_SESSION.update({"key": "", "ticked": [], "picks": [], "attempted": [], "miss": 0})
    first = select_up_to_n_decision(obs)
    second = select_up_to_n_decision(obs)
    third = select_up_to_n_decision(obs)
    clear_ocr = ocr.replace("This question is required\n", "")
    clear = Observation(**{**obs.__dict__, "ocr_text": clear_ocr})
    arrow = select_up_to_n_decision(clear)
    exact = exact_kb_option_decision(obs)
    labels = select_up_to_labels(obs)
    passed = bool(
        select_up_to_n_visible(ocr) and select_up_to_limit(ocr) == 3
        and is_garbage_option_label("ee")
        and first and first.get("action") == "select_option"
        and "required" not in str(first.get("target_text") or "").lower()
        and any("Helping" in x or "Summarising" in x or "Finding photos" in x for x in labels)
        and int((first.get("target_coords") or [0, 0])[1]) < 800
        and second and second.get("target_text") != first.get("target_text")
        and third and third.get("action") == "select_option"
        and arrow and arrow.get("action") == "click"
        and int((arrow.get("target_coords") or [0, 0])[0]) == 500
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
