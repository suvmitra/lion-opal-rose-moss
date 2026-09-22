# 20a_form_controls.py — fused form-control map and composite field workflows

_BIRTH_DATE_SESSION: dict[str, Any] = {
    "prompted": False,
    "filled": False,
    "value": None,
}

_MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _control_kind(node: dict[str, Any], text: str) -> str:
    cls = str(node.get("class") or "").lower()
    rid = str(node.get("resource_id") or "").lower()
    if node.get("editable") or any(token in cls for token in ("edittext", "textfield")):
        return "text_input"
    if node.get("checkable") or any(token in cls for token in ("checkbox", "radiobutton", "switch")):
        return "choice"
    if any(token in cls + " " + rid for token in ("spinner", "dropdown", "combobox", "select")):
        return "dropdown"
    if node.get("clickable") or "button" in cls:
        return "button"
    if text:
        return "label"
    return "unknown"


def map_form_controls(obs: Observation) -> list[dict[str, Any]]:
    """Fuse UIAutomator and OCR into one device-coordinate control map.

    Every control includes absolute bounds, a tap centre, a coarse grid cell,
    source and confidence. UIAutomator wins; OCR fills WebView accessibility gaps.
    """
    width = max(1, int(obs.image_width or obs.device_width or 1))
    height = max(1, int(obs.image_height or obs.device_height or 1))
    controls: list[dict[str, Any]] = []

    def append_control(node: dict[str, Any], source: str, confidence: float) -> None:
        bounds = node.get("bounds")
        if not isinstance(bounds, list) or len(bounds) != 4:
            return
        x1, y1, x2, y2 = [int(value) for value in bounds]
        if x2 <= x1 or y2 <= y1:
            return
        text = node_text(node).strip()
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        controls.append({
            "id": node.get("id"),
            "label": text,
            "kind": _control_kind(node, text),
            "bounds": [x1, y1, x2, y2],
            "center": [cx, cy],
            "milli": [int(cx * 1000 / width), int(cy * 1000 / height)],
            "grid": [min(5, int(cx * 6 / width)), min(9, int(cy * 10 / height))],
            "source": source,
            "confidence": confidence,
            "clickable": bool(node.get("clickable")),
            "editable": bool(node.get("editable")),
            "enabled": node.get("enabled") is not False,
        })

    for node in obs.ui_nodes or []:
        append_control(node, "uiautomator", 0.97)

    if obs.screenshot and Path(str(obs.screenshot)).exists():
        for node in ocr_line_nodes(Path(str(obs.screenshot)), psm=6):
            text = node_text(node).strip()
            if not text:
                continue
            bounds = node.get("bounds") or []
            duplicate = any(
                text.lower() == str(item.get("label") or "").lower()
                and isinstance(bounds, list)
                and abs(((bounds[0] + bounds[2]) // 2) - item["center"][0]) < 80
                and abs(((bounds[1] + bounds[3]) // 2) - item["center"][1]) < 60
                for item in controls
            )
            if not duplicate:
                append_control(node, "ocr", 0.78)

    controls.sort(key=lambda item: (item["center"][1], item["center"][0]))
    logger.info(
        "[FORM MAP] controls=%s ui=%s ocr=%s",
        len(controls),
        sum(item["source"] == "uiautomator" for item in controls),
        sum(item["source"] == "ocr" for item in controls),
    )
    return controls


def birth_date_question_visible(text: str) -> bool:
    compact = re.sub(r"\s+", " ", str(text or "").lower())
    asks_birth = any(token in compact for token in ("birth date", "date of birth", "your dob", "birthdate"))
    has_parts = all(token in compact for token in ("day", "month", "year"))
    return bool(asks_birth and has_parts)


def normalize_birth_date(value: Any) -> Optional[dict[str, str]]:
    """Return a validated DOB without ever deriving it from age or age range."""
    day: Any = None
    month: Any = None
    year: Any = None
    if isinstance(value, dict):
        day = value.get("day", value.get("dd"))
        month = value.get("month", value.get("mm"))
        year = value.get("year", value.get("yyyy"))
    elif isinstance(value, (list, tuple)) and len(value) >= 3:
        day, month, year = value[:3]
    elif value not in (None, ""):
        text = re.sub(r"[,]+", " ", str(value).strip())
        ymd = re.fullmatch(r"(19\d{2}|20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", text)
        dmy = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](19\d{2}|20\d{2})", text)
        named = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)\s+(19\d{2}|20\d{2})", text)
        if ymd:
            year, month, day = ymd.groups()
        elif dmy:
            day, month, year = dmy.groups()
        elif named:
            day, month, year = named.groups()
        else:
            return None

    try:
        day_i = int(str(day).strip())
        year_i = int(str(year).strip())
    except (TypeError, ValueError):
        return None

    month_text = str(month or "").strip()
    try:
        month_i = int(month_text)
    except ValueError:
        lowered = month_text.lower().rstrip(".")
        matches = [index for index, name in enumerate(_MONTH_NAMES, 1) if name.lower().startswith(lowered[:3])]
        if len(matches) != 1:
            return None
        month_i = matches[0]

    try:
        parsed = datetime(year_i, month_i, day_i)
    except (TypeError, ValueError):
        return None
    if year_i < 1900 or parsed > datetime.now():
        return None
    return {
        "day": str(day_i),
        "month": _MONTH_NAMES[month_i - 1],
        "month_number": str(month_i),
        "year": str(year_i),
        "iso": f"{year_i:04d}-{month_i:02d}-{day_i:02d}",
    }


def resolve_birth_date_fact(obs: Observation) -> Optional[dict[str, str]]:
    for key in ("date_of_birth", "birth_date", "dob"):
        value = (obs.kb or {}).get(key)
        resolved = normalize_birth_date(value)
        if resolved:
            logger.info("[KB AGENT] Resolved DOB from knowledge_base key=%s", key)
            return resolved
    for key in ("date_of_birth", "birth_date", "dob"):
        value = nested_scalar(obs.persona, key)
        resolved = normalize_birth_date(value)
        if resolved:
            logger.info("[KB AGENT] Resolved DOB from persona key=%s", key)
            return resolved
    combined = {
        "day": (obs.kb or {}).get("birth_day") or nested_scalar(obs.persona, "birth_day"),
        "month": (obs.kb or {}).get("birth_month") or nested_scalar(obs.persona, "birth_month"),
        "year": (obs.kb or {}).get("birth_year") or nested_scalar(obs.persona, "birth_year"),
    }
    resolved = normalize_birth_date(combined)
    if resolved:
        logger.info("[KB AGENT] Resolved DOB from separate day/month/year facts.")
        return resolved
    return None


def persist_birth_date_fact(value: dict[str, str], source: str) -> None:
    question = "Please provide your date of birth (Day, Month, Year)."
    basis = f"Human terminal input ({source})"
    for key, item in (
        ("date_of_birth", value["iso"]),
        ("birth_day", value["day"]),
        ("birth_month", value["month"]),
        ("birth_year", value["year"]),
    ):
        update_kb(
            key, item,
            reason="Operator supplied a missing composite personal fact.",
            provenance="declared", confidence=1.0,
            question=question, source_basis=basis,
        )


def prompt_birth_date_terminal() -> Optional[dict[str, str]]:
    if not stdin_can_prompt():
        logger.error("[MASTER AGENT] DOB is missing and interactive stdin is unavailable.")
        return None
    print("\n" + "=" * 78, flush=True)
    print("HUMAN INPUT REQUIRED — DATE OF BIRTH", flush=True)
    print("Enter the participant birth date as: DD Month YYYY", flush=True)
    print("Example format only: 11 June 1982", flush=True)
    print("Type 'skip' to stop without inventing personal data.", flush=True)
    print("=" * 78, flush=True)
    for attempt in range(1, HUMAN_INPUT_MAX_ATTEMPTS + 1):
        try:
            raw = input("Birth date> ").strip()
        except EOFError:
            return None
        if raw.lower() in SKIP_TOKENS:
            return None
        value = normalize_birth_date(raw)
        if value:
            persist_birth_date_fact(value, raw)
            print(f"Recorded: {value['day']} {value['month']} {value['year']}", flush=True)
            return value
        print(
            f"Invalid date. Use DD Month YYYY, for example 11 June 1982 "
            f"(attempt {attempt}/{HUMAN_INPUT_MAX_ATTEMPTS}).",
            flush=True,
        )
    return None


def _birth_date_part_coords(obs: Observation, controls: list[dict[str, Any]]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for part in ("day", "month", "year"):
        candidates = [
            item for item in controls
            if str(item.get("label") or "").strip().lower() == part
            and 120 <= int(item["milli"][1]) <= 760
        ]
        if candidates:
            candidates.sort(key=lambda item: (-float(item["confidence"]), item["milli"][1]))
            result[part] = list(candidates[0]["milli"])
    fallbacks = {"day": [130, 332], "month": [325, 332], "year": [525, 332]}
    for part, coords in fallbacks.items():
        result.setdefault(part, coords)
    return result


def birth_date_continue_coords(obs: Observation) -> list[int]:
    """Locate the saturated arrow button; retain a device-relative safe fallback."""
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        image = cv2.imread(str(obs.screenshot))
        if image is not None:
            height, width = image.shape[:2]
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, (35, 70, 70), (125, 255, 255))
            count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
            choices: list[tuple[float, list[int]]] = []
            for index in range(1, count):
                x, y, w, h, area = [int(v) for v in stats[index]]
                cx, cy = [float(v) for v in centroids[index]]
                if area < 700 or w < 70 or h < 20 or w / max(1, h) < 1.5:
                    continue
                mx, my = int(cx * 1000 / width), int(cy * 1000 / height)
                if not (300 <= mx <= 700 and 250 <= my <= 760):
                    continue
                score = area - abs(mx - 500) * 3 - abs(my - 390) * 2
                choices.append((score, [mx, my]))
            if choices:
                choices.sort(reverse=True)
                logger.info("[FORM MAP] DOB submit blob=%s", choices[0][1])
                return choices[0][1]
    return [500, 390]


def birth_date_controls_populated(obs: Observation, value: dict[str, str]) -> bool:
    visible = "\n".join(node_text(node) for node in (obs.ui_nodes or [])) + "\n" + str(obs.ocr_text or "")
    day_ok = bool(re.search(rf"(?<!\d){re.escape(value['day'])}(?!\d)", visible))
    month_ok = value["month"].lower() in visible.lower()
    year_ok = bool(re.search(rf"(?<!\d){re.escape(value['year'])}(?!\d)", visible))
    return day_ok and month_ok and year_ok


def birth_date_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not birth_date_question_visible(obs.ocr_text):
        _BIRTH_DATE_SESSION.update({"filled": False, "value": None})
        return None
    value = resolve_birth_date_fact(obs)
    if value is None and obs.screenshot is not None and not _BIRTH_DATE_SESSION.get("prompted"):
        _BIRTH_DATE_SESSION["prompted"] = True
        value = prompt_birth_date_terminal()
        if value:
            obs.kb = load_kb()
    if value is None:
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Date of birth is a personal fact and cannot be inferred from age.",
            "action": "request_human",
            "target_text": "",
            "missing_fact_key": "date_of_birth",
            "confidence_score": 1.0,
            "postcondition": "operator provides DD Month YYYY",
            "answer_provenance": "unknown",
            "source_basis": "No DOB in knowledge base or persona",
        }

    controls = map_form_controls(obs)
    continue_coords = birth_date_continue_coords(obs)
    if birth_date_controls_populated(obs, value) or (
        _BIRTH_DATE_SESSION.get("filled") and _BIRTH_DATE_SESSION.get("value") == value["iso"]
    ):
        return {
            "screen_state": "survey_question", "action": "click",
            "target_text": "right arrow / Continue",
            "target_coords": continue_coords, "coordinate_authoritative": True,
            "kb_key": "date_of_birth", "confidence_score": 0.98,
            "postcondition": "screen changed",
            "answer_reason": "All three DOB controls are populated; submit the form.",
        }
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": "Master agent resolved the complete DOB before asking the operator agent to act.",
        "action": "fill_date_parts",
        "target_text": "Birth Date: Day, Month, Year",
        "input_payload": value,
        "date_part_coords": _birth_date_part_coords(obs, controls),
        "continue_coords": continue_coords,
        "submit_after_fill": True,
        "kb_key": "date_of_birth", "kb_write": False,
        "confidence_score": 0.99,
        "postcondition": "screen changed",
        "answer_provenance": "declared",
        "source_basis": "Knowledge base/persona or formatted human terminal input",
    }


def _dropdown_value_matches(label: str, wanted: str, part: str) -> bool:
    left = re.sub(r"\s+", " ", str(label or "").strip()).lower()
    right = str(wanted or "").strip().lower()
    if part == "month":
        return left == right or (len(left) >= 3 and len(right) >= 3 and left[:3] == right[:3])
    return left == right


def _open_and_select_date_value(
    obs: Observation,
    part: str,
    wanted: str,
    milli_coords: list[int],
) -> bool:
    x, y = normalized_to_native(
        milli_coords, (obs.image_width, obs.image_height),
        (obs.device_width, obs.device_height),
    )
    logger.info("[OPERATOR AGENT] Open DOB %s at native=(%s,%s); choose %r", part, x, y, wanted)
    webview_click(x, y)
    time.sleep(0.45)

    for attempt in range(12):
        nodes = dump_ui_nodes()
        exact = [
            node for node in nodes
            if _dropdown_value_matches(node_text(node), wanted, part)
            and isinstance(node.get("bounds"), list)
            and node.get("enabled") is not False
        ]
        if exact:
            exact.sort(key=lambda node: (not bool(node.get("clickable")), node["bounds"][1]))
            tx, ty = node_center(exact[0])
            if ty < int(obs.device_height * 0.95):
                webview_click(tx, ty)
                time.sleep(0.45)
                return True

        try:
            shot, _, _, _, _ = capture_screenshot(obs.step + 6000 + attempt, save=False)
            lines = ocr_line_nodes(shot, psm=6)
        except Exception as exc:
            logger.debug("[DOB] OCR option scan failed: %s", exc)
            lines = []
        exact_lines = [line for line in lines if _dropdown_value_matches(node_text(line), wanted, part)]
        if exact_lines:
            tx, ty = node_center(exact_lines[0])
            if ty < int(obs.device_height * 0.95):
                webview_click(tx, ty)
                time.sleep(0.45)
                return True

        sx = int(obs.device_width * 0.50)
        sy1, sy2 = int(obs.device_height * 0.74), int(obs.device_height * 0.30)
        adb(["shell", "input", "swipe", str(sx), str(sy1), str(sx), str(sy2), "360"], timeout=15)
        time.sleep(0.28)
    logger.error("[OPERATOR AGENT] Could not select DOB %s=%r after bounded search.", part, wanted)
    adb(["shell", "input", "keyevent", "KEYCODE_BACK"], timeout=10)
    return False


def execute_birth_date_action(decision: dict[str, Any], obs: Observation) -> ActionResult:
    value = normalize_birth_date(decision.get("input_payload"))
    coords = decision.get("date_part_coords") or {}
    if value is None or not isinstance(coords, dict):
        return ActionResult(False, False, "fill_date_parts requires a validated DOB and mapped controls.")
    for part in ("day", "month", "year"):
        point = coords.get(part)
        if not (isinstance(point, list) and len(point) == 2):
            return ActionResult(False, False, f"Missing mapped coordinates for DOB {part}.")
        if not _open_and_select_date_value(obs, part, value[part], point):
            return ActionResult(False, True, f"Could not select DOB {part}={value[part]}.")

    nodes = dump_ui_nodes()
    try:
        shot, _, _, _, _ = capture_screenshot(obs.step + 6999, save=False)
        visible = "\n".join(node_text(node) for node in nodes) + "\n" + ocr(shot)
    except Exception:
        visible = "\n".join(node_text(node) for node in nodes)
    verified = (
        bool(re.search(rf"(?<!\d){re.escape(value['day'])}(?!\d)", visible))
        and value["month"].lower() in visible.lower()
        and bool(re.search(rf"(?<!\d){re.escape(value['year'])}(?!\d)", visible))
    )
    if not verified:
        return ActionResult(False, True, "DOB dropdown selections were not all visually verified.")

    _BIRTH_DATE_SESSION.update({"filled": True, "value": value["iso"]})
    if decision.get("submit_after_fill"):
        submit = decision.get("continue_coords") or [500, 390]
        sx, sy = normalized_to_native(
            submit, (obs.image_width, obs.image_height),
            (obs.device_width, obs.device_height),
        )
        logger.info("[OPERATOR AGENT] DOB verified; submit arrow native=(%s,%s)", sx, sy)
        webview_click(sx, sy)
        time.sleep(0.8)
    return ActionResult(True, True, "DOB Day/Month/Year selected, verified and submitted.")


def birth_date_regression_self_check() -> bool:
    text = "Would you like your opinion heard? Birth Date: Day Month Year"
    nodes = [
        {"id": 1, "text": "Day", "content_desc": "", "class": "Spinner", "resource_id": "",
         "bounds": [78, 657, 178, 700], "clickable": True, "editable": False, "enabled": True},
        {"id": 2, "text": "Month", "content_desc": "", "class": "Spinner", "resource_id": "",
         "bounds": [210, 657, 410, 700], "clickable": True, "editable": False, "enabled": True},
        {"id": 3, "text": "Year", "content_desc": "", "class": "Spinner", "resource_id": "",
         "bounds": [442, 657, 562, 700], "clickable": True, "editable": False, "enabled": True},
    ]
    obs = Observation(
        step=0, screenshot=None, image_width=955, image_height=2048,
        device_width=955, device_height=2048, screen_hash="dob-fixture",
        ocr_text=text, ui_nodes=nodes, kb={"date_of_birth": "1982-06-11"},
        persona={}, screen_phase="survey_question", survey_tiles=[],
    )
    decision = birth_date_decision(obs)
    mapped = map_form_controls(obs)
    passed = bool(
        normalize_birth_date("11 June 1982") == {
            "day": "11", "month": "June", "month_number": "6",
            "year": "1982", "iso": "1982-06-11",
        }
        and decision and decision.get("action") == "fill_date_parts"
        and decision.get("input_payload", {}).get("month") == "June"
        and decision.get("date_part_coords", {}).get("day")
        and len(mapped) >= 3
    )
    if passed:
        logger.info("[SELF-CHECK] Fused control-map and composite DOB routing checks passed.")
    else:
        logger.error("[SELF-CHECK] DOB routing failed: %s", decision)
    return passed
