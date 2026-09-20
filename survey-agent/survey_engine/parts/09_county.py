# 09_county.py — shared engine namespace (do not import directly)



def selected_answer_visual_signal(obs: Observation) -> bool:
    """Detect this survey's wide green selected-answer band, excluding Next."""
    if not obs.screenshot:
        return False
    path = Path(obs.screenshot)
    if not path.exists():
        return False
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            # Survey answers occupy the body. Excluding the lowest 17% prevents
            # the green circular Next button from looking like an answer.
            body = image.crop((0, int(height * 0.18), width, int(height * 0.83)))
            scaled_width = 240
            scaled_height = max(1, int(body.height * scaled_width / max(1, body.width)))
            body = body.resize((scaled_width, scaled_height), Image.Resampling.BILINEAR)
            pixels = body.load()
            longest_run = 0
            current_run = 0
            for y in range(body.height):
                green_pixels = 0
                for x in range(body.width):
                    red, green, blue = pixels[x, y]
                    if green >= 70 and green - red >= 25 and green - blue >= 8 and red < 150:
                        green_pixels += 1
                if green_pixels / body.width >= 0.28:
                    current_run += 1
                    longest_run = max(longest_run, current_run)
                else:
                    current_run = 0
            return longest_run >= 3
    except Exception as exc:
        logger.debug("Selected-answer visual detection unavailable: %s", exc)
        return False


def multi_select_question(obs: Observation) -> bool:
    text = re.sub(r"\s+", " ", obs.ocr_text.lower())
    if any(term in text for term in (
        "select all that apply", "choose all that apply", "select any that apply",
        "you may select more than one", "multiple answers", "select up to",
        "choose up to", "select at least", "choose at least",
        "which of these", "currently live with you",
    )):
        return True
    checkbox_count = sum(
        1 for node in obs.ui_nodes
        if node.get("checkable") and "checkbox" in str(node.get("class") or "").lower()
    )
    return checkbox_count >= 2


def matrix_semantic_hint(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if likert_slider_question_visible(ocr_text):
        return False
    return any(term in text for term in (
        "select one for each", "for each option", "for each row",
        "in each row", "select one in each row",
        "each of the following", "rate each", "select one answer per row",
        "one for each", "for each of the",
        "change in the types of bread", "types of bread bought",
        "strongly disagree", "strongly agree",
        "have never used", "within the past 12 months",
    ))


_MATRIX_SESSION: dict[str, Any] = {
    "active": False,
    "done": [],
    "scrolls": 0,
    "columns": [],
    "column_xs": [],
}
_VISUAL_RADIO_CACHE: dict[str, list[tuple[int, list[int]]]] = {}
MAX_MATRIX_SCROLLS = 8

MATRIX_NEVER_TERMS = (
    "electric car", "electric vehicle", "motorcycle", "scooter", "moped",
    "van", "truck", "cargo", "moving", "boat", "helicopter", "aircraft",
    "plane", "personal electric", "loaner", "zipcar", "car sharing",
    "another type",
)
MATRIX_RECENT_TERMS = (
    "personal car", "non-electric", "public transport", "subway", "bus",
    "train", "tram", "metro", "uber", "lyft", "ride hail", "taxi", "walk",
)
MATRIX_OCCASIONAL_TERMS = (
    "rented a car", "rental car", "hire a car",
)
MATRIX_SECTION_HEADERS = {
    "rentals", "public transit", "personal vehicles", "active travel",
    "shared mobility", "aviation", "water",
    "other paid transportation modes", "personal vehicles (i.e., vehicles you or someone",
}


def reset_matrix_session() -> None:
    _MATRIX_SESSION.update({
        "active": False, "done": [], "scrolls": 0, "columns": [], "column_xs": [],
    })


def visual_matrix_rows(obs: Observation) -> list[tuple[int, list[int]]]:
    """Find 4-column empty radio circles from the screenshot (WebView has no checkable)."""
    path = str(obs.screenshot or "")
    if path and path in _VISUAL_RADIO_CACHE:
        return _VISUAL_RADIO_CACHE[path]
    rows: list[tuple[int, list[int]]] = []
    if not path or not Path(path).exists():
        return rows
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            pixels = image.load()

            def is_ring(x: int, y: int) -> bool:
                red, green, blue = pixels[x, y]
                return abs(red - green) <= 12 and abs(green - blue) <= 12 and 140 <= red <= 220

            points: list[tuple[int, int]] = []
            for y in range(int(height * 0.16), int(height * 0.94), 2):
                runs: list[tuple[int, int]] = []
                start = None
                for x in range(int(width * 0.32), width - 8):
                    if is_ring(x, y):
                        if start is None:
                            start = x
                    else:
                        if start is not None and 2 <= (x - start) <= 12:
                            runs.append((start, x - 1))
                        start = None
                index = 0
                while index < len(runs) - 1:
                    left = runs[index][0]
                    right = runs[index + 1][1]
                    gap = runs[index + 1][0] - runs[index][1]
                    span = right - left
                    if 40 <= span <= 80 and 30 <= gap <= 70:
                        points.append(((left + right) // 2, y))
                        index += 2
                    else:
                        index += 1
            from collections import Counter, defaultdict
            x_bins = Counter(px // 20 for px, _ in points)
            top = [bin_x for bin_x, count in x_bins.most_common(6) if count >= 8]
            cols = sorted(
                bin_x * 20 + 10
                for bin_x, _ in sorted(((b, x_bins[b]) for b in top), key=lambda item: -item[1])[:4]
            )
            if len(cols) < 3:
                _VISUAL_RADIO_CACHE[path] = rows
                return rows
            y_bins: dict[int, list[int]] = defaultdict(list)
            for px, py in points:
                y_bins[py // 16].append(px)
            raw_rows: list[tuple[int, list[int]]] = []
            for y_key, xs in sorted(y_bins.items()):
                near = sum(1 for col in cols if any(abs(x - col) <= 30 for x in xs))
                if near >= 3:
                    raw_rows.append((y_key * 16 + 8, cols))
            merged: list[list[Any]] = []
            for y_center, col_xs in raw_rows:
                if not merged or y_center - merged[-1][0] > 40:
                    merged.append([y_center, col_xs, 1])
                else:
                    count = merged[-1][2]
                    merged[-1][0] = (merged[-1][0] * count + y_center) / (count + 1)
                    merged[-1][2] = count + 1
            rows = [(int(item[0]), list(item[1])) for item in merged]
    except Exception as exc:
        logger.debug("Visual matrix radios unavailable: %s", exc)
        rows = []
    if path:
        _VISUAL_RADIO_CACHE[path] = rows
        if rows:
            logger.info("[MATRIX] Visual radios rows=%s cols=%s", len(rows), rows[0][1] if rows else [])
    return rows


OCCUPATION_GROUP_OPTIONS = [
    "Higher managerial/ professional/ administrative (e.g. Doctor, Solicitor, Board Director)",
    "Intermediate managerial/ professional/ administrative (e.g. Board director small organisation, middle manager, principle officer in civil service)",
    "Supervisory or clerical/ junior managerial/ professional/ administrative (e.g. Office worker, Salesperson)",
    "Student",
    "Skilled manual worker (e.g. Carpenter, Plumber, Painter, Bus Driver, Pub/Bar worker)",
    "Semi or unskilled manual work (e.g. Manual worker, Caretaker, Park Keeper, Shop Assistant)",
    "Casual worker - not in permanent employment",
    "Housewife/ Home-maker",
    "Retired",
    "Farmer 1-49 acres",
    "Farmer 50+ acres",
    "Unemployed or not working due to long-term sickness",
]


def occupation_group_question_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if any(token in text for token in ("occupational group", "chief income earner")):
        return True
    hints = (
        "higher managerial", "intermediate managerial", "supervisory or clerical",
        "housewife", "home-maker", "casual worker", "skilled manual",
        "farmer 1-49", "farmer 50", "long-term sickness",
    )
    return sum(1 for hint in hints if hint in text) >= 2


def occupation_option_labels(ocr_text: str) -> list[str]:
    blob = re.sub(r"\s+", " ", str(ocr_text or "")).lower()
    found: list[str] = []
    for option in OCCUPATION_GROUP_OPTIONS:
        lowered = option.lower()
        if lowered in {"student", "retired"}:
            if re.search(rf"\b{re.escape(lowered)}\b", blob):
                found.append(option)
            continue
        tokens = [tok for tok in re.findall(r"[a-z0-9+]{4,}", lowered) if tok not in {
            "with", "from", "that", "this", "your", "professional", "administrative", "worker",
        }]
        if sum(1 for tok in tokens if tok in blob) >= 2:
            found.append(option)
            continue
        distinctive = (
            "middle manager", "board director", "solicitor", "office worker",
            "carpenter", "caretaker", "housewife", "home-maker",
            "casual worker", "farmer 1-49", "farmer 50",
        )
        if any(token in blob and token in lowered for token in distinctive):
            found.append(option)
    return found or list(OCCUPATION_GROUP_OPTIONS)


def infer_occupation_group_label(obs: Observation, options: list[str]) -> Optional[str]:
    stored = obs.kb.get("occupation_group") if isinstance(obs.kb, dict) else None
    if stored:
        status, matched = parse_human_answer_input(str(stored), options)
        if status == "ok" and matched:
            return matched[0]
    blob = " ".join([
        str((obs.kb or {}).get("current_title") or ""),
        str((obs.kb or {}).get("seniority_level") or ""),
        str((obs.persona or {}).get("current_title") or ""),
        str((obs.persona or {}).get("seniority_level") or ""),
        str(kb_or_persona_value(obs, "industry") or ""),
        str(kb_or_persona_value(obs, "employment_status") or ""),
    ]).lower()
    if any(token in blob for token in ("director", "solicitor", "board", "c-level", "ceo")):
        wanted = "higher managerial"
    elif any(token in blob for token in (
        "manager", "lead", "scientist", "professional", "senior", "management",
        "information technology", "software",
    )):
        wanted = "middle manager"
    else:
        wanted = "intermediate managerial"
    status, matched = parse_human_answer_input(wanted, options)
    if status == "ok" and matched:
        return matched[0]
    for option in options:
        if "intermediate" in option.lower() or "middle manager" in option.lower():
            return option
    return options[1] if len(options) > 1 else (options[0] if options else None)


def occupation_group_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not occupation_group_question_visible(obs.ocr_text):
        return None
    options = option_labels_from_observation(obs) or list(OCCUPATION_GROUP_OPTIONS)
    target = infer_occupation_group_label(obs, options)
    if not target:
        return None
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "")).lower()
    visible = any(
        token in blob for token in (
            "middle manager", "intermediate managerial", "higher managerial",
            "supervisory", "student", "housewife", "retired", "farmer",
        ) if token in target.lower()
    ) or any(part.lower() in blob for part in re.findall(r"[A-Za-z]{5,}", target)[:3])
    if not visible:
        lower_screen = any(token in blob for token in ("retired", "farmer", "unemployed", "housewife", "sickness"))
        logger.info("[OCCUPATION] %r not on screen; scrolling %s", target, "up" if lower_screen else "down")
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Scroll until the occupation radio is visible.",
            "action": "scroll_up" if lower_screen else "scroll_down",
            "confidence_score": 0.9,
            "postcondition": "screen changed",
            "kb_key": "occupation_group",
        }
    coords = body_option_coords(obs, "middle manager" if "intermediate" in target.lower() else target.split("(")[0].strip())
    logger.info("[OCCUPATION] Selecting %r coords=%s", target, coords)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": "Chief-income-earner occupation from persona/KB (middle manager).",
        "action": "select_option",
        "target_element_id": None,
        "target_text": target,
        "target_coords": coords or [180, 620],
        "coordinate_authoritative": True,
        "input_payload": target,
        "kb_key": "occupation_group",
        "kb_write": True,
        "confidence_score": 0.96,
        "postcondition": f"selected option is {target}",
        "answer_provenance": "declared",
        "source_basis": "knowledge_base.json:current_title/seniority_level",
        "selection_complete": True,
    }


_COUNTY_SESSION: dict[str, Any] = {"picked": False}

IRISH_COUNTIES = (
    "Carlow", "Cavan", "Clare", "Cork", "Donegal", "Dublin", "Galway",
    "Kerry", "Kildare", "Kilkenny", "Laois", "Leitrim", "Limerick",
    "Longford", "Louth", "Mayo", "Meath", "Monaghan", "Offaly",
    "Roscommon", "Sligo", "Tipperary", "Waterford", "Westmeath",
    "Wexford", "Wicklow",
)


def county_question_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if any(token in text for token in (
        "following counties", "which county", "counties do you currently",
        "what county", "county do you live", "which region do you live",
        "region do you live in",
    )):
        return True
    return county_dropdown_open(ocr_text)


def county_dropdown_open(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "")).lower()
    hits = sum(1 for name in IRISH_COUNTIES if re.search(rf"\b{name.lower()}\b", blob))
    return hits >= 4


def intended_county(obs: Observation) -> str:
    for key in ("county", "city", "town"):
        raw = str(kb_or_persona_value(obs, key) or "").strip()
        if not raw:
            continue
        lowered = raw.lower()
        if "dublin" in lowered:
            return "Dublin"
        for name in IRISH_COUNTIES:
            if name.lower() == lowered or f"county {name.lower()}" == lowered:
                return name
    postal = str((obs.kb or {}).get("postal_code") or (obs.kb or {}).get("area_code") or "").upper()
    if re.match(r"D\d", postal):
        return "Dublin"
    return "Dublin"


def county_name_in_text(text: str) -> list[str]:
    found: list[str] = []
    blob = str(text or "")
    for name in IRISH_COUNTIES:
        if re.search(rf"\b{re.escape(name)}\b", blob, flags=re.I) and name not in found:
            found.append(name)
    return found


def county_from_ui_and_screenshot(obs: Observation) -> Optional[str]:
    """Closed combo value from UI nodes and the combo band — not the red banner OCR."""
    if county_dropdown_open(obs.ocr_text):
        return None
    wanted = intended_county(obs)
    names: list[str] = []
    height = max(1, int(obs.image_height or obs.device_height or 1))
    for node in obs.ui_nodes or []:
        bounds = node.get("bounds") or []
        if len(bounds) == 4:
            cy = ((int(bounds[1]) + int(bounds[3])) / 2) / height
            if cy < 0.28 or cy > 0.70:
                continue
        names.extend(county_name_in_text(node_text(node)))
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        try:
            for psm in (11, 6, 3):
                for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                    bounds = node.get("bounds") or []
                    if len(bounds) != 4:
                        continue
                    cy = ((int(bounds[1]) + int(bounds[3])) / 2) / height
                    if cy < 0.34 or cy > 0.62:
                        continue
                    names.extend(county_name_in_text(node_text(node)))
        except Exception as exc:
            logger.debug("County combo screenshot OCR: %s", exc)
    names.extend(county_name_in_text(obs.ocr_text))
    lowered = [n.lower() for n in names]
    if wanted.lower() in lowered:
        return wanted
    uniq = list(dict.fromkeys(names))
    return uniq[0] if len(uniq) == 1 else None


def county_displayed_value(obs: Observation) -> Optional[str]:
    return county_from_ui_and_screenshot(obs)


def county_picked_visual(obs: Observation) -> bool:
    """Orange selected row in the county list (Dublin), not the 12% progress bar."""
    for bar in orange_cta_milli(obs, 0.16, 0.72):
        if 160 <= int(bar[1]) <= 720:
            return True
    return False


def county_list_context(obs: Observation) -> bool:
    """County list even when OCR is only the status bar."""
    if county_question_visible(obs.ocr_text) or county_dropdown_open(obs.ocr_text):
        return True
    if _COUNTY_SESSION.get("picked"):
        return True
    if len(visible_counties_in_ocr_order(obs.ocr_text)) >= 2:
        return True
    bottom = orange_cta_milli(obs, 0.84, 0.98)
    mid = orange_cta_milli(obs, 0.16, 0.84)
    return bool(bottom and mid)


def county_continue_coords(obs: Observation) -> Optional[list[int]]:
    """Sticky footer Continue = lowest orange bar, never the selected county row."""
    bars = orange_cta_milli(obs, 0.84, 0.98)
    if bars:
        return [500, max(860, max(int(b[1]) for b in bars))]
    found = continue_button_on_screen(obs)
    if found and int(found[0][1]) >= 860:
        return found[0]
    if "continue" in re.sub(r"\s+", " ", str(obs.ocr_text or "").lower()):
        return [500, 910]
    return [500, 910] if bars or orange_cta_milli(obs, 0.86, 0.98) else None


def county_selection_complete(obs: Observation) -> bool:
    wanted = intended_county(obs).lower()
    if not county_dropdown_open(obs.ocr_text):
        shown = county_displayed_value(obs)
        if shown and shown.lower() != wanted:
            _COUNTY_SESSION["picked"] = False
            return False
        if shown and shown.lower() == wanted:
            _COUNTY_SESSION["picked"] = True
            return True
    if county_picked_visual(obs) or _COUNTY_SESSION.get("picked"):
        _COUNTY_SESSION["picked"] = True
        return True
    return False


def county_dropdown_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not county_list_context(obs):
        _COUNTY_SESSION["picked"] = False
        return None
    wanted = intended_county(obs)
    shown = county_displayed_value(obs)
    if county_selection_complete(obs) and not county_dropdown_open(obs.ocr_text):
        logger.info("[COUNTY] %s already selected; grounding Continue.", wanted)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"County {wanted} is selected from knowledge_base city.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Continue »",
            "target_coords": county_continue_coords(obs) or [500, 875],
            "coordinate_authoritative": True,
            "kb_key": "county",
            "kb_write": True,
            "input_payload": wanted,
            "confidence_score": 0.97,
            "postcondition": "screen changed",
            "answer_provenance": "declared",
            "source_basis": "knowledge_base.json:city",
            "selection_complete": True,
        }
    list_open = county_dropdown_open(obs.ocr_text) or bool(
        orange_cta_milli(obs, 0.16, 0.84) and orange_cta_milli(obs, 0.84, 0.98)
    )
    if list_open:
        _COUNTY_OPEN_TRIES["county"] = 0
        cont = county_continue_coords(obs)
        dcoords = county_option_coords(obs, wanted)
        if dcoords and int(dcoords[1]) < 840:
            logger.info("[COUNTY] Tapping list value %r coords=%s", wanted, dcoords)
            _COUNTY_SESSION["picked"] = True
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": f"Select {wanted} from the county list.",
                "action": "select_option",
                "target_text": wanted,
                "target_coords": dcoords,
                "coordinate_authoritative": True,
                "input_payload": wanted,
                "kb_key": "county",
                "kb_write": True,
                "confidence_score": 0.98,
                "postcondition": f"selected option is {wanted}",
                "selection_complete": True,
            }
        if cont and int(cont[1]) >= 860:
            logger.info("[COUNTY] Sticky Continue at %s (not a county row)", cont)
            _COUNTY_SESSION["picked"] = True
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": f"{wanted} chosen; tap the footer Continue bar, not a county row.",
                "action": "click",
                "target_text": "Continue",
                "target_coords": cont,
                "coordinate_authoritative": True,
                "kb_key": "county",
                "input_payload": wanted,
                "confidence_score": 0.97,
                "postcondition": "screen changed",
                "selection_complete": True,
            }
        if county_picked_visual(obs) or _COUNTY_SESSION.get("picked"):
            logger.info("[COUNTY] %s is selected; scroll down until Continue is visible.", wanted)
            return {
                "screen_state": "survey_question",
                "action": "scroll_down",
                "list_scroll": True,
                "confidence_score": 0.93,
                "postcondition": "screen changed",
                "kb_key": "county",
                "answer_reason": f"{wanted} is selected; scroll down to Continue.",
            }
        blob = str(obs.ocr_text or "")
        coords = dcoords
        if coords is None or not re.search(rf"\b{re.escape(wanted)}\b", blob, flags=re.I):
            return county_list_scroll_action(obs, wanted)
        logger.info("[COUNTY] Tapping list value %r coords=%s", wanted, coords)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Select {wanted} from the county dropdown (knowledge_base.json:city).",
            "action": "select_option",
            "target_element_id": None,
            "target_text": wanted,
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": wanted,
            "kb_key": "county",
            "kb_write": True,
            "confidence_score": 0.98,
            "postcondition": f"selected option is {wanted}",
            "answer_provenance": "declared",
            "source_basis": "knowledge_base.json:city",
            "selection_complete": True,
        }
    coords = county_combo_coords(obs)
    field = shown or "Select one..."
    _COUNTY_OPEN_TRIES["county"] = _COUNTY_OPEN_TRIES.get("county", 0) + 1
    logger.info("[COUNTY] Opening dropdown via %r coords=%s attempt=%s",
                field, coords, _COUNTY_OPEN_TRIES["county"])
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Open the county dropdown showing {field} and choose {wanted}.",
        "action": "open_dropdown",
        "target_element_id": None,
        "target_text": field,
        "target_coords": coords,
        "coordinate_authoritative": True,
        "input_payload": wanted,
        "kb_key": "county",
        "confidence_score": 0.95,
        "postcondition": "dropdown is open",
        "answer_provenance": "declared",
        "source_basis": "knowledge_base.json:city",
    }


def county_combo_coords(obs: Observation) -> list[int]:
    """Tap the closed spinner on the visible value (Donegal / Select one), not empty pink space."""
    labels = []
    shown = county_displayed_value(obs)
    if shown:
        labels.append(shown)
    labels.extend(["Select one...", "Select one"])
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        try:
            for wanted in labels:
                for psm in (11, 6, 3):
                    for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                        label = re.sub(r"\s+", " ", node_text(node)).strip()
                        if not re.search(rf"\b{re.escape(wanted)}\b", label, flags=re.I):
                            continue
                        bounds = node.get("bounds") or []
                        if len(bounds) != 4 or in_header_chrome(bounds, obs.image_height):
                            continue
                        x1, y1, x2, y2 = [int(v) for v in bounds]
                        cy = ((y1 + y2) / 2) / max(1, obs.image_height)
                        if cy < 0.30 or cy > 0.70:
                            continue
                        # Chevron sits to the right of the county word.
                        nx = int(min(x2 + 36, x1 + max(80, (x2 - x1) * 0.85)) * 1000 / max(1, obs.image_width))
                        ny = int(((y1 + y2) / 2) * 1000 / max(1, obs.image_height))
                        return [max(140, min(420, nx)), max(400, min(540, ny))]
        except Exception as exc:
            logger.debug("County combo OCR unavailable: %s", exc)
    attempt = _COUNTY_OPEN_TRIES.get("county", 0)
    fallbacks = (
        [200, 455],
        [175, 468],
        [230, 442],
        [190, 430],
        [250, 470],
        [210, 490],
    )
    return list(fallbacks[attempt % len(fallbacks)])


def visible_counties_in_ocr_order(ocr_text: str) -> list[str]:
    found: list[str] = []
    for token in re.findall(r"[A-Za-z]+", str(ocr_text or "")):
        for name in IRISH_COUNTIES:
            if name.lower() == token.lower() and name not in found:
                found.append(name)
                break
    return found


def county_index(name: str) -> int:
    lowered = str(name or "").strip().lower()
    for i, item in enumerate(IRISH_COUNTIES):
        if item.lower() == lowered:
            return i
    return -1


def county_option_coords(obs: Observation, county: str) -> Optional[list[int]]:
    wanted = str(county or "").strip()
    if not wanted:
        return None
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        try:
            for psm in (11, 6, 3):
                for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                    label = re.sub(r"\s+", " ", node_text(node)).strip()
                    if not re.search(rf"\b{re.escape(wanted)}\b", label, flags=re.I):
                        continue
                    bounds = node.get("bounds") or []
                    if len(bounds) != 4 or in_header_chrome(bounds, obs.image_height):
                        continue
                    x1, y1, x2, y2 = [int(v) for v in bounds]
                    ny = int(((y1 + y2) / 2) * 1000 / max(1, obs.image_height))
                    if ny < 80 or ny > 920:
                        continue
                    nx = int((x1 + 24) * 1000 / max(1, obs.image_width))
                    return [max(70, min(260, nx)), max(100, min(900, ny))]
        except Exception as exc:
            logger.debug("County OCR unavailable: %s", exc)
    visible = visible_counties_in_ocr_order(obs.ocr_text)
    if wanted not in visible:
        return None
    idx = visible.index(wanted)
    n = max(1, len(visible))
    ny = int(90 + (idx + 0.45) / n * 800)
    return [150, max(110, min(880, ny))]


def county_list_scroll_action(obs: Observation, wanted: str) -> dict[str, Any]:
    visible = visible_counties_in_ocr_order(obs.ocr_text)
    wanted_i = county_index(wanted)
    vis_i = [county_index(name) for name in visible if county_index(name) >= 0]
    if vis_i and wanted_i >= 0 and min(vis_i) > wanted_i:
        action = "scroll_up"
        reason = f"List starts at {visible[0]} (after {wanted}); scroll up."
    else:
        action = "scroll_down"
        reason = f"Scroll the county list until {wanted} is visible."
    logger.info("[COUNTY] %s visible=%s", reason, visible[:8])
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": reason,
        "action": action,
        "list_scroll": True,
        "confidence_score": 0.92,
        "postcondition": "screen changed",
        "kb_key": "county",
    }

