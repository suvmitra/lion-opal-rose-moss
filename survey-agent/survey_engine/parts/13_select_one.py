# 13_select_one.py — shared engine namespace (do not import directly)



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
    return any(term in text for term in (
        "select one", "select only one", "choose one", "employment status",
        "please select one of the below", "please select an answer",
        "are you?", "buy another brand of bread",
        "occupational group", "chief income earner",
        "higher managerial", "intermediate managerial",
        "following counties", "which county",
        "not available in a store",
    ))


def hovis_unavailable_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return "hovis" in blob and ("not available" in blob or "buy another brand" in blob)


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
        "kb_key": "hovis_unavailable_action",
        "confidence_score": 0.88,
        "postcondition": "screen changed",
        "selection_complete": True,
    }


def single_choice_radio_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tap the recommended radio, then Continue. Retarget on miss; keys as last resort."""
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
            labels = option_labels_from_ocr(obs)
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
            "kb_key": "hovis_unavailable_action",
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
    logger.info("[SELECT ONE] select_then_continue pick=%r taps=%s continue=%s gray=%s",
                pick, tap_points, continue_coords, gray_rows)
    _SELECT_ONE_SESSION["taps"] = int(_SELECT_ONE_SESSION.get("taps") or 0) + 1
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Tap {pick} on the gray row, then Continue.",
        "action": "select_then_continue",
        "target_element_id": None,
        "target_text": pick,
        "target_coords": circle,
        "tap_points": tap_points,
        "continue_coords": continue_coords,
        "coordinate_authoritative": True,
        "input_payload": pick,
        "kb_key": "hovis_unavailable_action",
        "kb_write": False,
        "confidence_score": 0.95,
        "postcondition": "screen changed",
        "selection_complete": True,
    }
