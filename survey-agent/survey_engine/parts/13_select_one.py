# 13_select_one.py — shared engine namespace (do not import directly)

_INSTRUCTION_LIKERT = (
    "Neither agree nor disagree",
    "Somewhat disagree",
    "Somewhat agree",
    "Strongly disagree",
    "Strongly agree",
)
_LIKERT_ROWS = (
    "Strongly agree",
    "Somewhat agree",
    "Neither agree nor disagree",
    "Somewhat disagree",
    "Strongly disagree",
)


def quoted_select_pick(ocr_text: str) -> str:
    """Read 'Please select the X option' and return the named visible choice."""
    head = re.sub(r"[\s,|]+", " ", str(ocr_text or ""))[:320]
    match = re.search(r"select the\s+(.+?)\s+option", head, re.I)
    fragment = re.sub(r"[^a-z\s]", " ", (match.group(1) if match else "").lower())
    fragment = re.sub(r"\s+", " ", fragment).strip()
    if not fragment:
        return ""
    best, best_n = "", 0
    for label in _INSTRUCTION_LIKERT:
        words = label.lower().split()
        if all(re.search(rf"\b{re.escape(word)}\b", fragment) for word in words):
            if len(words) > best_n:
                best, best_n = label, len(words)
    return best


def quoted_select_instruction_visible(ocr_text: str) -> bool:
    text = re.sub(r"[\s,|]+", " ", str(ocr_text or "").lower())
    if "select the" in text and "option" in text and quoted_select_pick(ocr_text):
        return True
    return "from the below" in text and bool(quoted_select_pick(ocr_text))


def looks_like_single_choice(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if maxdiff_question_visible(ocr_text) or select_all_apply_visible(ocr_text):
        return False
    if any(term in text for term in (
        "select one for each", "for each option", "for each row",
        "in each row", "select one in each row",
        "each of the following", "select one answer per row",
        "types of bread bought",
    )):
        return False
    if quoted_select_instruction_visible(ocr_text):
        return True
    if adult_age_question_visible(ocr_text) or re.search(r"what age are you|enter a whole number", text):
        return False
    return any(term in text for term in (
        "select one", "select only one", "choose one", "employment status",
        "please select one of the below", "please select an answer",
        "are you?", "buy another brand of bread",
        "occupational group", "chief income earner",
        "higher managerial", "intermediate managerial",
        "following counties", "which county",
        "not available in a store",
        "brand of smartphone", "smartphone do you currently",
        "which brand of",
        "would you agree", "do you agree to share",
    ))


def hovis_unavailable_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return "hovis" in blob and ("not available" in blob or "buy another brand" in blob)


def dark_option_row_milli(obs: Observation) -> list[list[int]]:
    """Left-radio centres of stacked dark Qualtrics option cards."""
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return []
    try:
        image = cv2.imread(path)
        if image is None:
            return []
        height, width = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 0, 35), (180, 110, 160))
        mask[: int(height * 0.20), :] = 0
        mask[int(height * 0.78):, :] = 0
        row = (mask > 0).sum(axis=1)
        need = int(width * 0.22)
        bands: list[tuple[int, int]] = []
        in_bar, start = False, 0
        for y, count in enumerate(row):
            if count >= need and not in_bar:
                in_bar, start = True, y
            elif count < need and in_bar:
                in_bar = False
                if y - start >= int(height * 0.028):
                    bands.append((start, y))
        if in_bar and int(height * 0.78) - start >= int(height * 0.028):
            bands.append((start, int(height * 0.78)))
        rows = [[180, int(((top + bot) // 2) * 1000 / height)] for top, bot in bands[:8]]
        if rows:
            logger.info("[QUOTED SELECT] Dark card rows milli=%s", rows)
        return rows
    except Exception as exc:
        logger.debug("[QUOTED SELECT] Dark-row scan failed: %s", exc)
        return []


def red_continue_milli(obs: Observation) -> Optional[list[int]]:
    """Right-hand red Continue (not the left Back sibling)."""
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return None
    try:
        image = cv2.imread(path)
        if image is None:
            return None
        height, width = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (0, 90, 90), (12, 255, 255)) | cv2.inRange(
            hsv, (168, 90, 90), (180, 255, 255)
        )
        mask[: int(height * 0.55), :] = 0
        mask[int(height * 0.90):, :] = 0
        row = (mask > 0).sum(axis=1)
        need = int(width * 0.10)
        best_y, best_n = 0, 0
        for y, count in enumerate(row):
            if count > best_n:
                best_n, best_y = count, y
        if best_n < need:
            return None
        xs = [x for x in range(0, width, 3) if mask[best_y, x] > 0]
        if not xs:
            return None
        right = xs[len(xs) // 2 :]
        cx = (right[0] + right[-1]) // 2
        milli = [int(cx * 1000 / width), int(best_y * 1000 / height)]
        if milli[0] < 520:
            milli[0] = 680
        if 600 <= milli[1] <= 880:
            logger.info("[QUOTED SELECT] Red Continue milli=%s", milli)
            return milli
        return None
    except Exception as exc:
        logger.debug("[QUOTED SELECT] Red Continue scan failed: %s", exc)
        return None


def quoted_select_row_milli(obs: Observation, pick: str) -> list[int]:
    ocr = select_one_ocr_row_milli(obs, pick)
    if ocr and 250 <= int(ocr[1]) <= 760:
        return [180, int(ocr[1])]
    rows = dark_option_row_milli(obs) or gray_radio_row_milli(obs)
    idx = _LIKERT_ROWS.index(pick) if pick in _LIKERT_ROWS else 3
    if rows:
        if len(rows) >= len(_LIKERT_ROWS):
            return [180, int(rows[idx][1])]
        return [180, int(rows[min(idx, len(rows) - 1)][1])]
    return [180, 350 + idx * 72]


def quoted_select_continue_milli(obs: Observation) -> list[int]:
    found = continue_button_on_screen(obs)
    if found and 600 <= int(found[0][1]) <= 880:
        return [max(560, int(found[0][0])), int(found[0][1])]
    red = red_continue_milli(obs)
    if red:
        return red
    bars = orange_cta_milli(obs, 0.62, 0.90)
    if bars:
        return [680, min(860, max(int(b[1]) for b in bars))]
    return [680, 780]


def quoted_instruction_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Instruction names the answer in quotes: tap that radio, then red Continue."""
    if not quoted_select_instruction_visible(obs.ocr_text):
        return None
    pick = quoted_select_pick(obs.ocr_text)
    if not pick:
        return None
    obs.screen_phase = "survey_question"
    key = question_fingerprint(obs)
    if _SELECT_ONE_SESSION.get("key") != key:
        _SELECT_ONE_SESSION.update({"key": key, "taps": 0, "misses": 0, "verified": False})
    continue_coords = quoted_select_continue_milli(obs)
    if int(continue_coords[1]) >= 900:
        continue_coords = [680, 780]
    tapped = int(_SELECT_ONE_SESSION.get("taps") or 0) >= 1 or _SELECT_ONE_SESSION.get("verified")
    if tapped:
        logger.info("[QUOTED SELECT] %r already tapped; Continue at %s", pick, continue_coords)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Instruction option {pick} is selected; tap Continue.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Continue »",
            "target_coords": continue_coords,
            "coordinate_authoritative": True,
            "input_payload": pick,
            "kb_key": "instruction_select",
            "confidence_score": 0.97,
            "postcondition": "screen changed",
            "selection_complete": True,
        }
    row = quoted_select_row_milli(obs, pick)
    circle = [180, int(row[1])]
    tap_points = [circle, [260, int(row[1])], [420, int(row[1])]]
    _SELECT_ONE_SESSION["taps"] = int(_SELECT_ONE_SESSION.get("taps") or 0) + 1
    logger.info("[QUOTED SELECT] ASK=%r THEREFORE radio=%s then Continue=%s",
                pick, circle, continue_coords)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"The question names {pick}; tap that radio, then Continue.",
        "action": "select_then_continue",
        "target_element_id": None,
        "target_text": pick,
        "target_coords": circle,
        "tap_points": tap_points,
        "continue_coords": continue_coords,
        "coordinate_authoritative": True,
        "input_payload": pick,
        "kb_key": "instruction_select",
        "kb_write": False,
        "confidence_score": 0.96,
        "postcondition": "screen changed",
        "selection_complete": True,
    }


def select_one_ocr_row_milli(obs: Observation, pick: str) -> Optional[list[int]]:
    """Milli coords of the option's gray row in the screenshot body (not the nav bar)."""
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists() or not pick:
        return None
    needle = re.sub(r"\s+", " ", pick.lower())[:28]
    h = max(1, int(obs.image_height or 1))
    w = max(1, int(obs.image_width or 1))
    for psm in (6, 11, 3):
        try:
            nodes = ocr_line_nodes(Path(path), psm=psm)
        except Exception:
            nodes = []
        for node in nodes:
            bounds = node.get("bounds") or []
            if len(bounds) != 4:
                continue
            x1, y1, x2, y2 = [int(v) for v in bounds]
            if y1 < h * 0.24 or y2 > h * 0.80:
                continue
            label = re.sub(r"\s+", " ", node_text(node).lower())
            if needle[:10] not in label and label not in needle:
                continue
            cy = (y1 + y2) // 2
            cx = (x1 + x2) // 2
            return [int(cx * 1000 / w), int(cy * 1000 / h)]
    return None


def gray_radio_row_milli(obs: Observation) -> list[list[int]]:
    """Milli [circle_x, row_y] for each gray Qualtrics option row in the body."""
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return []
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            pixels = image.load()
            y0, y1 = int(height * 0.36), int(height * 0.78)
            x0, x1 = int(width * 0.10), int(width * 0.90)
            bands: list[tuple[int, int]] = []
            in_band = False
            start = y0
            for y in range(y0, y1, 3):
                hits = samples = 0
                for x in range(x0, x1, 6):
                    r, g, b = pixels[x, y]
                    samples += 1
                    if 155 <= r <= 220 and 155 <= g <= 220 and 155 <= b <= 220 and abs(r - g) < 22 and abs(g - b) < 22:
                        hits += 1
                gray = samples and hits / samples >= 0.42
                if gray and not in_band:
                    in_band = True
                    start = y
                elif (not gray) and in_band:
                    in_band = False
                    if y - start >= 36:
                        bands.append((start, y))
            if in_band and y1 - start >= 36:
                bands.append((start, y1))
            rows: list[list[int]] = []
            for top, bot in bands[:6]:
                cy = (top + bot) // 2
                rows.append([int(width * 0.14 * 1000 / width), int(cy * 1000 / height)])
            logger.info("[SELECT ONE] Gray rows milli=%s from %s bands", rows, len(bands))
            return rows
    except Exception as exc:
        logger.debug("[SELECT ONE] Gray-row scan failed: %s", exc)
        return []


def select_one_keyboard_decision(obs: Observation, pick: str) -> dict[str, Any]:
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": "Coordinate taps missed; TAB/SPACE then TAB/ENTER to Continue.",
        "action": "focus_select_continue",
        "target_text": pick,
        "target_coords": None,
        "input_payload": pick,
        "kb_key": "hovis_unavailable_action" if hovis_unavailable_visible(obs.ocr_text) else observation_kb_key(obs),
        "confidence_score": 0.88,
        "postcondition": "screen changed",
        "selection_complete": True,
    }


def single_choice_radio_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tap the recommended radio, then Continue. Retarget on miss; keys as last resort."""
    region = irish_region_radio_decision(obs)
    if region:
        return region
    quoted = quoted_instruction_decision(obs)
    if quoted:
        return quoted
    phone = smartphone_brand_decision(obs)
    if phone:
        return phone
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if select_all_apply_visible(obs.ocr_text):
        return None
    if not (looks_like_single_choice(obs.ocr_text) or hovis_unavailable_visible(obs.ocr_text)):
        return None
    obs.screen_phase = "survey_question"
    pick = "Buy another brand of bread"
    if "buy another brand" not in blob:
        if "wait and go" in blob:
            pick = "Wait and go to another store to buy Hovis"
        elif "don't buy" in blob or "do not buy" in blob:
            pick = "Don't buy any bread"
        else:
            labels = [
                lab for lab in option_labels_from_ocr(obs)
                if not is_progression_cta(lab) and "next question" not in lab.lower()
            ]
            pick = pick_option_assumption(labels) or ""
            if not pick:
                return None
    key = question_fingerprint(obs)
    if _SELECT_ONE_SESSION.get("key") != key:
        _SELECT_ONE_SESSION.update({"key": key, "taps": 0, "misses": 0, "verified": False})
    unanswered = "please select an answer" in blob
    if _SELECT_ONE_SESSION.get("verified") or ((not unanswered) and select_all_lime_band_count(obs) >= 1):
        found = maxdiff_continue_coords(obs) or continue_button_on_screen(obs)
        coords = found[0] if found else [500, 778]
        label = found[1] if found and len(found) > 1 else "Continue »"
        logger.info("[SELECT ONE] Option is in; Continue at %s", coords)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Select-one is filled; tap Continue.",
            "action": "click",
            "target_element_id": None,
            "target_text": label,
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": pick,
            "kb_key": "hovis_unavailable_action" if hovis_unavailable_visible(obs.ocr_text) else observation_kb_key(obs),
            "confidence_score": 0.96,
            "postcondition": "screen changed",
            "selection_complete": True,
        }
    misses = int(_SELECT_ONE_SESSION.get("misses") or 0)
    if misses >= 2:
        logger.info("[SELECT ONE] Coordinate compound missed; TAB/SPACE/ENTER for %r", pick)
        return select_one_keyboard_decision(obs, pick)
    gray_rows = gray_radio_row_milli(obs)
    ocr_milli = select_one_ocr_row_milli(obs, pick)
    first_row = gray_rows[0] if gray_rows else (ocr_milli or [140, 493])
    circle = [140, first_row[1]]
    text_pt = [500, first_row[1]]
    if misses == 1 and len(gray_rows) > 0:
        circle = [180, first_row[1] + 8]
        text_pt = [420, first_row[1]]
    continue_coords = [500, 778]
    found = maxdiff_continue_coords(obs) or continue_button_on_screen(obs)
    if found:
        continue_coords = found[0]
        if int(continue_coords[1]) >= 900:
            continue_coords = [500, 778]
    tap_points = [circle, text_pt, [220, first_row[1]]]
    logger.info("[SELECT ONE] answer-only pick=%r taps=%s gray=%s", pick, tap_points, gray_rows)
    _SELECT_ONE_SESSION["taps"] = int(_SELECT_ONE_SESSION.get("taps") or 0) + 1
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Tap {pick}; verify this same question is selected before Continue.",
        "action": "select_option",
        "target_element_id": None,
        "target_text": pick,
        "target_coords": circle,
        "tap_points": tap_points,
        "coordinate_authoritative": False,
        "input_payload": pick,
        "kb_key": "hovis_unavailable_action" if hovis_unavailable_visible(obs.ocr_text) else observation_kb_key(obs),
        "kb_write": False,
        "confidence_score": 0.95,
        "postcondition": f"selected option is {pick}",
        "selection_complete": True,
    }


def gender_radio_list(obs: Observation) -> bool:
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    return bool(re.search(
        r"please select an answer|select one of the below|non-binary|gender fluid|prefer not to say",
        blob,
    ))


def gender_continue_milli(obs: Observation) -> Optional[list[int]]:
    """Mid-screen orange Continue (~y=45%). Never footer y=87% / dump y=92%."""
    for bar in orange_cta_milli(obs, 0.34, 0.62):
        if 360 <= int(bar[1]) <= 580:
            return [int(bar[0]), int(bar[1])]
    ocr = visible_continue_milli(obs)
    if ocr and 360 <= int(ocr[1]) <= 580:
        return ocr
    return None


def gender_male_milli(obs: Observation) -> list[int]:
    mapped = mapped_option_milli(obs, "Male") if "mapped_option_milli" in globals() else None
    if mapped and 160 <= int(mapped[1]) <= 820:
        return [int(mapped[0]), int(mapped[1])]
    path = str(obs.screenshot or "")
    if path and Path(path).exists():
        center = ocr_text_center(Path(path), "Male")
        if center:
            x = int(center[0] * 1000 / max(1, obs.image_width))
            y = int(center[1] * 1000 / max(1, obs.image_height))
            if 150 <= y <= 820 and 60 <= x <= 700:
                return [max(180, x), y]
    return [280, 320]


def gender_screen_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tap the stored gender (Male), never Female/Other, then the footer Next."""
    if not gender_choice_screen(obs):
        return None
    intended = str((obs.kb or {}).get("gender") or "Male").strip() or "Male"
    if intended.lower() in {"other", "female"}:
        intended = "Male"
    selected = False
    if "selected_option_visual" in globals():
        selected = bool(selected_option_visual(obs, intended))
    if not selected:
        selected = any(
            (n.get("checked") or n.get("selected"))
            and re.fullmatch(re.escape(intended), node_text(n).strip(), re.I)
            for n in obs.ui_nodes
        )
    if selected:
        blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
        if "next question" in blob:
            found = continue_button_on_screen(obs) if "continue_button_on_screen" in globals() else None
            coords = list(found[0]) if found else [740, 890]
            text = "Next question"
        else:
            mid = gender_continue_milli(obs)
            coords = list(mid) if mid else [500, 455]
            if int(coords[1]) > 620:
                coords = [500, 455]
            text = "Continue"
        logger.info("[GENDER] %s selected; %s at %s", intended, text, coords)
        return {
            "screen_state": "survey_question", "action": "click", "target_text": text,
            "target_coords": coords, "coordinate_authoritative": True, "target_element_id": None,
            "kb_key": "gender", "confidence_score": 0.97, "postcondition": "screen changed",
            "selection_complete": True, "skip_object_grounding": True,
            "answer_reason": f"{intended} is the checked row; tap {text}.",
        }
    coords = gender_male_milli(obs)
    logger.info("[GENDER] Tap %s at %s; do not accept Female or Other.", intended, coords)
    return {
        "screen_state": "survey_question", "action": "select_option", "target_text": intended,
        "target_coords": coords, "coordinate_authoritative": True, "input_payload": intended,
        "kb_key": "gender", "confidence_score": 0.97, "target_element_id": None,
        "postcondition": f"selected option is {intended}", "selection_complete": False,
        "skip_object_grounding": True,
        "answer_reason": f"Stored gender is {intended}. Tap that row, never Female or Other.",
    }


_DEVICE_BRAND_CACHE = {"raw": None}


def smartphone_brand_question_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return ("smartphone" in text or "mobile phone" in text) and (
        "brand" in text or "currently use" in text
    )


def cached_device_brand() -> str:
    if _DEVICE_BRAND_CACHE["raw"] is not None:
        return str(_DEVICE_BRAND_CACHE["raw"])
    parts: list[str] = []
    for prop in ("ro.product.brand", "ro.product.manufacturer", "ro.product.model"):
        try:
            parts.append(adb_text(["shell", "getprop", prop], timeout=3).strip())
        except Exception:
            parts.append("")
    _DEVICE_BRAND_CACHE["raw"] = " ".join(p for p in parts if p)
    logger.info("[PHONE] getprop=%r", _DEVICE_BRAND_CACHE["raw"])
    return str(_DEVICE_BRAND_CACHE["raw"])


def map_device_to_phone_option(raw: str, labels: list[str]) -> str:
    blob = (raw or "").lower()
    wanted = "Samsung" if not blob else "Other Android phone"
    for needle, label in (
        ("samsung", "Samsung"), ("google", "Google Pixel"), ("pixel", "Google Pixel"),
        ("xiaomi", "Xiaomi / Redmi"), ("redmi", "Xiaomi / Redmi"), ("poco", "Xiaomi / Redmi"),
        ("oppo", "Oppo / OnePlus"), ("oneplus", "Oppo / OnePlus"), ("realme", "Oppo / OnePlus"),
        ("apple", "Apple iPhone"), ("iphone", "Apple iPhone"),
    ):
        if needle in blob:
            wanted = label
            break
    for lab in labels:
        low = lab.lower()
        if wanted.lower() == low or wanted.lower() in low or low in wanted.lower():
            return lab
    token = wanted.split()[0].lower()
    for lab in labels:
        if token in lab.lower():
            return lab
    return wanted


def smartphone_continue_milli(obs: Observation) -> list[int]:
    for name in ("purple_submit_arrow_milli", "mapped_age_arrow_milli"):
        fn = globals().get(name)
        if not callable(fn):
            continue
        hit = fn(obs)
        if hit and 400 <= int(hit[1]) <= 920:
            return [int(hit[0]), int(hit[1])]
    found = continue_button_on_screen(obs)
    if found and 500 <= int(found[0][1]) <= 920:
        return [int(found[0][0]), int(found[0][1])]
    return [500, 860]


def mapped_option_milli(obs: Observation, pick: str) -> Optional[list[int]]:
    if not pick or "build_screen_object_map" not in globals():
        return None
    try:
        scene = build_screen_object_map(obs)
    except Exception:
        return None
    needle = pick.lower()[:8]
    for item in scene.get("controls") or []:
        label = str(item.get("label") or "").lower()
        milli = list(item.get("visual_milli") or item.get("milli") or [])
        if needle[:6] in label and len(milli) == 2 and 220 <= int(milli[1]) <= 820:
            return [int(milli[0]), int(milli[1])]
    return None


def smartphone_brand_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Read ADB brand, persist to KB, tap that card, then the purple arrow."""
    if not smartphone_brand_question_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    labels = option_labels_from_ocr(obs)
    stored = str((obs.kb or {}).get("smartphone_brand") or "").strip()
    raw = stored or cached_device_brand()
    pick = map_device_to_phone_option(raw, labels)
    write = not stored or stored != pick
    key = question_fingerprint(obs)
    if _SELECT_ONE_SESSION.get("key") != key:
        _SELECT_ONE_SESSION.update({"key": key, "taps": 0, "misses": 0, "verified": False})
    missing = survey_validation_error(obs)
    tapped = int(_SELECT_ONE_SESSION.get("taps") or 0) >= 1 and not missing
    arrow = smartphone_continue_milli(obs)
    if tapped:
        logger.info("[PHONE] %r already tapped; arrow %s", pick, arrow)
        return {
            "screen_state": "survey_question", "action": "click", "target_text": "Continue",
            "target_coords": arrow, "coordinate_authoritative": True,
            "input_payload": pick, "kb_key": "smartphone_brand", "kb_write": write,
            "confidence_score": 0.97, "postcondition": "screen changed",
            "answer_reason": f"{pick} selected; tap the purple arrow.",
            "skip_object_grounding": True, "object_kind": "button",
        }
    row = mapped_option_milli(obs, pick) or select_one_ocr_row_milli(obs, pick)
    order = ["Samsung", "Apple iPhone", "Google Pixel", "Xiaomi / Redmi",
             "Oppo / OnePlus", "Other Android phone"]
    idx = next((i for i, name in enumerate(order) if pick.lower()[:6] in name.lower()), 0)
    tap = list(row) if row else [500, 370 + idx * 68]
    tap = [max(180, min(820, int(tap[0]))), int(tap[1])]
    _SELECT_ONE_SESSION["taps"] = int(_SELECT_ONE_SESSION.get("taps") or 0) + 1
    logger.info("[PHONE] device/KB → %r tap=%s arrow=%s write=%s", pick, tap, arrow, write)
    return {
        "screen_state": "survey_question", "action": "select_then_continue",
        "target_text": pick, "target_coords": tap, "coordinate_authoritative": True,
        "tap_points": [tap, [500, tap[1]], [220, tap[1]]], "continue_coords": arrow,
        "input_payload": pick, "kb_key": "smartphone_brand", "kb_write": write,
        "confidence_score": 0.96, "postcondition": "screen changed",
        "answer_reason": f"Device brand maps to {pick}; tap the card then the purple arrow.",
        "answer_provenance": "declared",
        "source_basis": "adb getprop / knowledge_base.json:smartphone_brand",
        "skip_object_grounding": True, "object_kind": "choice",
    }
