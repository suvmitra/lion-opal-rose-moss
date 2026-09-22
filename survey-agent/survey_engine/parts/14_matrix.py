# 14_matrix.py — shared engine namespace (do not import directly)



def drag_drop_question_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return any(token in text for token in (
        "drag and drop", "drag & drop", "drop the number",
        "into the square", "into the box",
    ))


def captcha_code_question_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return any(token in text for token in (
        "type the following code", "type the code", "enter the code",
        "following code in the text", "captcha", "verification code",
        "security code", "type the following",
    ))


def matrix_grid_visible(obs: Observation) -> bool:
    if maxdiff_question_visible(obs.ocr_text):
        return False
    if captcha_code_question_visible(obs.ocr_text) or drag_drop_question_visible(obs.ocr_text):
        return False
    if occupation_group_question_visible(obs.ocr_text):
        return False
    if county_question_visible(obs.ocr_text):
        return False
    if children_count_question_visible(obs.ocr_text):
        return False
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if "welcome to" in blob and "click continue" in blob:
        return False
    if likert_slider_question_visible(obs.ocr_text, obs.ui_nodes):
        return False
    if looks_like_single_choice(obs.ocr_text):
        return False
    if matrix_semantic_hint(obs.ocr_text):
        return True
    visual = visual_matrix_rows(obs)
    if visual and len(visual[0][1]) >= 3:
        return True
    ui_rows = cluster_matrix_rows(matrix_cell_nodes(obs), obs)
    return bool(ui_rows and len(ui_rows[0]) >= 3)



def survey_validation_error(obs: Observation) -> bool:
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    return any(term in text for term in (
        "please fill in this field",
        "this field is required",
        "fill in this field",
        "please provide an answer",
        "please rate at least",
        "rate at least",
        "problems with some of the data",
        "questions with errors",
        "you must select",
        "required question",
        "this question is required",
        "question is required",
        "an answer is required",
    ))


def matrix_fill_map(obs: Observation, rows: list[list[dict[str, Any]]]) -> dict[int, bool]:
    """True when a visual row already has a teal/cyan filled radio."""
    filled: dict[int, bool] = {}
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists() or not rows:
        return filled
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            pixels = image.load()
            column_xs = _MATRIX_SESSION.get("column_xs") or [
                int(node_center(cell)[0]) for cell in rows[0]
            ]
            for row in rows:
                row_y = int(sum(node_center(cell)[1] for cell in row) / max(1, len(row)))
                is_filled = False
                for col_x in column_xs:
                    hits = 0
                    for dy in range(-8, 9, 2):
                        for dx in range(-8, 9, 2):
                            xx, yy = int(col_x) + dx, row_y + dy
                            if 0 <= xx < width and 0 <= yy < height:
                                red, green, blue = pixels[xx, yy]
                                if red < 110 and green > 130 and blue > 120:
                                    hits += 1
                    if hits >= 5:
                        is_filled = True
                        break
                filled[row_y] = is_filled
    except Exception as exc:
        logger.debug("Matrix fill map unavailable: %s", exc)
    filled_n = sum(1 for value in filled.values() if value)
    logger.info("[MATRIX] Visual fill %s/%s rows already answered.", filled_n, len(filled))
    return filled


def matrix_cell_nodes(obs: Observation) -> list[dict[str, Any]]:
    """WebView matrix radios are often clickable circles with checkable=false."""
    cells: list[dict[str, Any]] = []
    for node in obs.ui_nodes:
        if not node.get("enabled"):
            continue
        if not (node.get("checkable") or node.get("clickable")):
            continue
        label = node_text(node).strip()
        if label and (is_progression_cta(label) or is_forbidden_progression_target(label)):
            continue
        if label and len(label) > 28:
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            continue
        width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        if width < 18 or height < 18:
            continue
        if width > obs.image_width * 0.22 or height > obs.image_height * 0.09:
            continue
        center_y = (bounds[1] + bounds[3]) / 2
        if center_y < obs.image_height * 0.16 or center_y > obs.image_height * 0.94:
            continue
        cells.append(node)
    return cells


def cluster_matrix_rows(
    cells: list[dict[str, Any]], obs: Observation
) -> list[list[dict[str, Any]]]:
    if not cells:
        return []
    tolerance = max(22, int(obs.image_height * 0.015))
    rows: list[list[dict[str, Any]]] = []
    for node in sorted(cells, key=lambda item: node_center(item)[1]):
        center_y = node_center(node)[1]
        if not rows:
            rows.append([node])
            continue
        row_center = sum(node_center(item)[1] for item in rows[-1]) / len(rows[-1])
        if abs(center_y - row_center) > tolerance:
            rows.append([node])
        else:
            rows[-1].append(node)
    return [sorted(row, key=lambda item: node_center(item)[0]) for row in rows if len(row) >= 3]


def visual_rows_as_cells(obs: Observation) -> list[list[dict[str, Any]]]:
    rows: list[list[dict[str, Any]]] = []
    for y_center, xs in visual_matrix_rows(obs):
        row = []
        for index, x_center in enumerate(xs):
            row.append({
                "id": None,
                "text": "",
                "content_desc": "",
                "class": "visual-radio",
                "bounds": [x_center - 28, y_center - 28, x_center + 28, y_center + 28],
                "clickable": True,
                "checkable": False,
                "checked": False,
                "editable": False,
                "enabled": True,
                "selected": False,
                "visual_col": index,
            })
        if len(row) >= 3:
            rows.append(row)
    return rows


def matrix_radio_rows(obs: Observation) -> list[list[dict[str, Any]]]:
    visual = visual_rows_as_cells(obs)
    ui_rows = cluster_matrix_rows(matrix_cell_nodes(obs), obs)
    if visual and (not ui_rows or len(visual) >= len(ui_rows)):
        return visual
    return ui_rows


def matrix_column_labels(obs: Observation, column_count: int) -> list[str]:
    stored = _MATRIX_SESSION.get("columns") or []
    if (
        stored and len(stored) >= max(3, column_count)
        and "never" in str(stored[0]).lower()
    ):
        return stored[:column_count]
    text = re.sub(r"\s+", " ", obs.ocr_text)
    known = [
        "No, I have never used",
        "Yes, more than 3 years ago",
        "Yes, 1-3 years ago",
        "Yes, within the past 12 months",
        "Strongly disagree",
        "Disagree",
        "Neutral",
        "Agree",
        "Strongly agree",
        "Yes",
        "No",
    ]
    lowered = text.lower()
    found = [label for label in known if label.lower() in lowered]
    recency = [
        "No, I have never used",
        "Yes, more than 3 years ago",
        "Yes, 1-3 years ago",
        "Yes, within the past 12 months",
    ]
    collapsed = re.sub(r"\s+", " ", obs.ocr_text.lower())
    if column_count >= 3 and any(term in collapsed for term in (
        "never used", "12 month", "select one for each", "3 years ago", "1-3 year",
    )):
        _MATRIX_SESSION["columns"] = recency
        return recency[:column_count]
    found = [label for label in found if label.lower() not in {"yes", "no"}]
    if len(found) >= column_count:
        return found[:column_count]
    if found:
        return found
    if stored:
        return stored[:column_count]
    return recency[:column_count] if column_count >= 3 else [f"col_{index}" for index in range(column_count)]


def matrix_row_label(obs: Observation, row: list[dict[str, Any]]) -> str:
    if not row:
        return ""
    row_y = sum(node_center(item)[1] for item in row) / len(row)
    first_x = min(node.get("bounds")[0] for node in row if node.get("bounds"))
    best = ""
    best_delta = 10**9
    sources = list(obs.ui_nodes)
    for node in sources:
        label = node_text(node).strip()
        if not label or len(label) < 4:
            continue
        if is_progression_cta(label) or is_forbidden_progression_target(label):
            continue
        lowered = re.sub(r"\s+", " ", label.lower())
        if any(lowered.startswith(header) for header in MATRIX_SECTION_HEADERS):
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            continue
        center_x = (bounds[0] + bounds[2]) / 2
        center_y = (bounds[1] + bounds[3]) / 2
        if center_x >= first_x - 4:
            continue
        delta = abs(center_y - row_y)
        if delta < best_delta and delta <= max(48, int(obs.image_height * 0.035)):
            best_delta = delta
            best = label
    return best


def choose_matrix_column(
    row_label: str,
    columns: list[str],
    obs: Optional["Observation"] = None,
) -> str:
    """Persona/KB-aware recency pick for one matrix row."""
    if not columns:
        return ""
    row = row_label.lower()
    n = len(columns)
    never_col = columns[0]
    recent_col = columns[-1]
    mid_col = columns[min(2, n - 1)]
    for col in columns:
        lowered = col.lower()
        if "never" in lowered:
            never_col = col
        if "12 month" in lowered or "past year" in lowered:
            recent_col = col
        if "1-3" in lowered or "1 – 3" in lowered or "1 to 3" in lowered:
            mid_col = col
    if any(term in row for term in MATRIX_NEVER_TERMS) and "non-electric" not in row:
        return never_col
    if any(term in row for term in MATRIX_OCCASIONAL_TERMS):
        return mid_col
    if any(term in row for term in MATRIX_RECENT_TERMS):
        return recent_col
    if "bicycle" in row:
        return never_col
    return never_col


def configured_matrix_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Fill one matrix row per cycle from persona/KB, scroll until Continue."""
    if looks_like_single_choice(obs.ocr_text) or not matrix_grid_visible(obs):
        if _MATRIX_SESSION.get("active"):
            reset_matrix_session()
            logger.info("[MATRIX] Left grid for a normal question; KB/persona routers may answer.")
        return None
    rows = matrix_radio_rows(obs)
    if not rows:
        if not matrix_semantic_hint(obs.ocr_text):
            reset_matrix_session()
            return None
        _MATRIX_SESSION["active"] = True
        if _MATRIX_SESSION.get("scrolls", 0) < MAX_MATRIX_SCROLLS:
            _MATRIX_SESSION["scrolls"] = int(_MATRIX_SESSION.get("scrolls") or 0) + 1
            logger.info("[MATRIX] Grid not parsed; scrolling (%s/%s).", _MATRIX_SESSION["scrolls"], MAX_MATRIX_SCROLLS)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": "Matrix grid is still open; scroll to keep filling rows.",
                "action": "scroll_down",
                "target_element_id": None, "target_text": None, "target_coords": None,
                "input_payload": None, "kb_key": None, "kb_write": False,
                "missing_fact_key": None, "confidence_score": 0.9,
                "postcondition": "screen changed",
                "visual_reasoning": "Sticky matrix session: keep scrolling until Continue is visible.",
            }
        return None
    _MATRIX_SESSION["active"] = True
    columns = matrix_column_labels(obs, len(rows[0]))
    if columns and not str(columns[0]).startswith("col_"):
        _MATRIX_SESSION["columns"] = columns
    _MATRIX_SESSION["column_xs"] = [int(node_center(cell)[0]) for cell in rows[0]]
    fill_map = matrix_fill_map(obs, rows)
    done = {re.sub(r"\s+", " ", item).strip().lower() for item in _MATRIX_SESSION.get("done") or []}
    remaining = []
    for row in rows:
        label = matrix_row_label(obs, row)
        key = re.sub(r"\s+", " ", label).strip().lower()
        if not key or re.fullmatch(r"y\d+", key):
            continue
        if any(key.startswith(header) for header in MATRIX_SECTION_HEADERS):
            continue
        row_y = int(sum(node_center(item)[1] for item in row) / max(1, len(row)))
        visually_filled = bool(fill_map.get(row_y)) or any(
            abs(row_y - filled_y) <= 24 and fill_map[filled_y] for filled_y in fill_map
        )
        if visually_filled:
            continue
        if key in done and not survey_validation_error(obs):
            continue
        remaining.append((label, key, row))
    if not remaining:
        continue_now = survey_next_decision(obs)
        if (
            continue_now
            and continue_now.get("action") == "click"
            and not survey_validation_error(obs)
        ):
            logger.info("[MATRIX] Visible rows filled; Continue is grounded.")
            return continue_now
        if _MATRIX_SESSION.get("scrolls", 0) < MAX_MATRIX_SCROLLS:
            _MATRIX_SESSION["scrolls"] = int(_MATRIX_SESSION.get("scrolls") or 0) + 1
            logger.info("[MATRIX] Visible rows filled; scrolling (%s/%s).", _MATRIX_SESSION["scrolls"], MAX_MATRIX_SCROLLS)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": "More matrix rows are below the fold.",
                "action": "scroll_down",
                "target_element_id": None, "target_text": None, "target_coords": None,
                "input_payload": None, "kb_key": None, "kb_write": False,
                "missing_fact_key": None, "confidence_score": 0.95,
                "postcondition": "screen changed",
                "visual_reasoning": "Keep scrolling a long matrix until Continue is visible.",
            }
        logger.info("[MATRIX] Scroll budget exhausted; advancing.")
        return continue_now or survey_next_decision(obs)

    label, key, row = remaining[0]
    column = choose_matrix_column(label, columns, obs)
    try:
        col_index = columns.index(column)
    except ValueError:
        col_index = 0 if "never" in column.lower() else len(row) - 1
    col_index = min(max(col_index, 0), len(row) - 1)
    cell = row[col_index]
    cx, cy = node_center(cell)
    coords = [
        int(max(0, min(1000, cx * 1000 / max(1, obs.image_width)))),
        int(max(0, min(1000, cy * 1000 / max(1, obs.image_height)))),
    ]
    logger.info(
        "[MATRIX] Row %r -> %r coords=%s remaining_after=%s scrolls=%s",
        label or key, column, coords, len(remaining) - 1, _MATRIX_SESSION.get("scrolls"),
    )
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": (
            f"Persona/KB recency pick for {label or 'this row'}: {column}."
        ),
        "action": "select_matrix_cell",
        "target_element_id": None,
        "target_text": column,
        "target_coords": coords,
        "coordinate_authoritative": True,
        "row_text": label,
        "column_text": column,
        "input_payload": column,
        "kb_key": None,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.9,
        "postcondition": "matrix cell selected",
        "visual_reasoning": "Local matrix router fills one row per cycle from persona/KB.",
        "answer_provenance": "inferred",
        "source_basis": "knowledge_base.json + persona recency policy",
        "inference_confidence": 0.78,
        "selection_complete": False,
        "matrix_row_key": key,
        "matrix_row_label": label or key,
    }


def matrix_question(obs: Observation) -> bool:
    if likert_slider_question_visible(obs.ocr_text):
        return False
    return matrix_grid_visible(obs)


def matrix_question_complete(obs: Observation) -> bool:
    checkables = [
        node for node in obs.ui_nodes
        if node.get("checkable") and isinstance(node.get("bounds"), list)
    ]
    if not checkables:
        return False
    tolerance = max(18, int(obs.image_height * 0.012))
    rows: list[list[dict[str, Any]]] = []
    for node in sorted(checkables, key=lambda item: node_center(item)[1]):
        center_y = node_center(node)[1]
        if not rows:
            rows.append([node])
            continue
        row_center = sum(node_center(item)[1] for item in rows[-1]) / len(rows[-1])
        if abs(center_y - row_center) > tolerance:
            rows.append([node])
        else:
            rows[-1].append(node)
    meaningful_rows = [row for row in rows if len(row) >= 2]
    return bool(meaningful_rows) and all(
        any(node.get("checked") or node.get("selected") for node in row)
        for row in meaningful_rows
    )


def answer_already_selected(obs: Observation) -> bool:
    """Combine structured and visual evidence of an answered radio/choice row."""
    if matrix_question(obs):
        return matrix_question_complete(obs)
    if multi_select_question(obs):
        # A checked checkbox is not proof that all intended choices are done.
        # The action decision must explicitly mark selection_complete=true.
        return False
    for node in obs.ui_nodes:
        if not (node.get("checked") or node.get("selected")):
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            continue
        center_y = (bounds[1] + bounds[3]) / 2
        if center_y < obs.image_height * 0.85:
            return True
    return selected_answer_visual_signal(obs)


def green_continue_pill_coords(obs: Observation, y0: float = 0.38, y1: float = 0.90) -> Optional[list[int]]:
    """Lime Continue pill in a Y band. Keyboard-up uses 0.36-0.62 so we do not tap the IME."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return None
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            w, h = rgb.size
            pixels = rgb.load()
            best = None
            best_score = 0
            for y in range(int(h * y0), int(h * y1), 3):
                xs = [x for x in range(int(w * 0.18), int(w * 0.82), 3) if _lime_pixel(*pixels[x, y])]
                if len(xs) < 10:
                    continue
                span = (xs[-1] - xs[0]) / max(1, w)
                if 0.14 <= span <= 0.52:
                    cx = (xs[0] + xs[-1]) / 2
                    if len(xs) > best_score:
                        best_score = len(xs)
                        best = [int(cx * 1000 / w), int(y * 1000 / h)]
            if best and 300 <= best[1] <= 840:
                return best
    except Exception:
        return None
    return None


def visual_progression_coords(obs: Observation) -> list[int]:
    """Find a prominent colored bottom CTA when text/accessibility is absent."""
    fallback = [500, 875]
    if not obs.screenshot or not Path(obs.screenshot).exists():
        return fallback
    try:
        image = cv2.imread(str(obs.screenshot))
        if image is None:
            return fallback
        height, width = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (20, 45, 55), (175, 255, 250))
        keyboard = soft_keyboard_visible(obs)
        cut = 0.30 if keyboard else 0.55
        y_lo, y_hi = (0.30, 0.68) if keyboard else (0.60, 0.94)
        mask[: int(height * cut), :] = 0
        if keyboard:
            mask[int(height * 0.70):, :] = 0
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        candidates: list[tuple[float, float, float]] = []
        for index in range(1, count):
            x, y, component_width, component_height, area = [int(v) for v in stats[index]]
            center_x, center_y = [float(v) for v in centroids[index]]
            if area < width * height * 0.003:
                continue
            if not (height * y_lo <= center_y <= height * y_hi):
                continue
            centrality = 1.0 - min(1.0, abs(center_x / max(1, width) - 0.5) * 2)
            width_score = min(1.0, component_width / max(1, width * 0.55))
            area_score = min(1.0, area / max(1, width * height * 0.08))
            score = centrality * 0.45 + width_score * 0.35 + area_score * 0.20
            candidates.append((score, center_x, center_y))
        if candidates:
            _, center_x, center_y = max(candidates)
            return [
                int(max(0, min(1000, center_x * 1000 / max(1, width)))),
                int(max(0, min(1000, center_y * 1000 / max(1, height)))),
            ]
    except Exception as exc:
        logger.debug("Visual progression grounding unavailable: %s", exc)
    return fallback


def soft_keyboard_visible(obs: Observation) -> bool:
    markers = ("honeyboard", "inputmethod", "latinime", "keyboard")
    for node in obs.ui_nodes:
        descriptor = " ".join(
            str(node.get(key) or "") for key in ("package", "resource_id", "class")
        ).lower()
        if any(marker in descriptor for marker in markers):
            bounds = node.get("bounds") or []
            if len(bounds) == 4 and bounds[3] >= obs.image_height * 0.72:
                return True
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if "english (us)" in blob or "english(us)" in blob:
        return True
    if re.search(r"\bq\s*w\s*e\s*r\s*t\s*y\s*u\s*i\s*o\s*p\b", blob):
        return True
    return False


def repair_ocr_i_am(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"(?i)(^|[\s|@])[|l1i]\s*am\b", r"\1I am", value)
    value = value.replace("| am", "I am").replace("|am", "I am")
    return value


def question_fingerprint(obs: Observation) -> str:
    question = repair_ocr_i_am(current_question_text(obs)).lower()
    question = re.sub(r"\b\d{1,2}:\d{2}\b", " ", question)
    question = re.sub(r"\b\d{1,3}%\b", " ", question)
    question = re.sub(r"[^a-z0-9 ?]+", " ", question)
    question = re.sub(r"\s+", " ", question).strip()
    if "any other" in question and "brand" in question:
        return "bread_brands_other"
    if "how open" in question and "loyalty" in question:
        return "loyalty_program_openness"
    if ranking_question_visible(obs.ocr_text) and "emerald" in question:
        return "membership_tier_rank"
    if likert_slider_question_visible(obs.ocr_text):
        return "likert_tier_like_dislike"
    if "?" in question:
        question = question[: question.rfind("?") + 1][-160:]
    return question[-160:]


def question_select_issued(obs: Observation) -> bool:
    key = question_fingerprint(obs)
    if _LAST_SELECT_FINGERPRINT.get(key):
        return True
    signature = semantic_screen_signature(obs)
    return bool(_LAST_SELECT_FINGERPRINT.get(signature) or _MULTI_SELECT_PROGRESS.get(signature))


def teal_radio_filled(obs: Observation) -> bool:
    """True when a cyan/teal filled radio is visible in the answer body."""
    if open_text_question_visible(obs.ocr_text) or soft_keyboard_visible(obs):
        return False
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return False
    try:
        with Image.open(path) as source:
            image = source.convert("RGB")
            width, height = image.size
            x0, x1 = int(width * 0.03), int(width * 0.22)
            y0, y1 = int(height * 0.20), int(height * 0.82)
            pixels = image.load()
            hits = 0
            for y in range(y0, y1, 3):
                for x in range(x0, x1, 3):
                    red, green, blue = pixels[x, y]
                    if red < 100 and green > 140 and blue > 130 and (green - red) > 45:
                        hits += 1
                        if hits >= 12:
                            logger.info("[RADIO] Teal filled control detected hits=%s", hits)
                            return True
    except Exception as exc:
        logger.debug("Teal radio detection unavailable: %s", exc)
    return False


def ranking_required_count(ocr_text: str) -> int:
    match = re.search(r"rate at least\s+(\d+)", str(ocr_text or "").lower())
    return int(match.group(1)) if match else 3


def ranking_complete(obs: Observation) -> bool:
    if not ranking_question_visible(obs.ocr_text):
        return False
    items = ranking_item_labels(obs)
    done = _RANK_PROGRESS.get(question_fingerprint(obs), [])
    need = max(ranking_required_count(obs.ocr_text), len(items) if items else 3)
    return len(done) >= need


def required_answer_missing(obs: Observation) -> bool:
    """True when Continue would submit an empty Select-one / validation-error page."""
    if likert_slider_question_visible(obs.ocr_text):
        return not likert_complete(obs)
    if ranking_question_visible(obs.ocr_text):
        return not ranking_complete(obs)
    if open_text_question_visible(obs.ocr_text) and open_text_field_empty(obs):
        return True
    if open_text_needs_more_words(obs) and not (
        (not open_text_field_empty(obs)) and (
        _OPEN_TEXT_TYPED.get(question_fingerprint(obs))
        or _OPEN_TEXT_TYPED.get(open_text_screen_key(obs))
        or _OPEN_TEXT_DONE.get(open_text_screen_key(obs)))
    ):
        return True
    if county_question_visible(obs.ocr_text):
        return not county_selection_complete(obs)
    if survey_validation_error(obs):
        if open_text_question_visible(obs.ocr_text) and not open_text_field_empty(obs) and (
            open_text_box_has_answer(obs)
            or _OPEN_TEXT_TYPED.get(open_text_screen_key(obs))
            or _OPEN_TEXT_DONE.get(open_text_screen_key(obs))
        ):
            return False
        return True
    if teal_radio_filled(obs) or question_select_issued(obs) or answer_already_selected(obs):
        return False
    if not looks_like_single_choice(obs.ocr_text):
        return False
    return len(option_labels_from_observation(obs)) >= 2


def inferred_preference_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Pick a persona-aligned visible option for ordinary Select-one questions."""
    if obs.screen_phase != "survey_question":
        return None
    if matrix_grid_visible(obs):
        return None
    options = option_labels_from_observation(obs)
    if len(options) < 2:
        return None
    question = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    pick = None
    policies = (
        (("loyalty program", "joining loyalty", "how open are you"),
         ("very open", "very interested", "strongly agree")),
        (("how likely",), ("very likely", "extremely likely")),
        (("how often",), ("always", "very often", "frequently")),
    )
    for hints, preferred in policies:
        if any(hint in question for hint in hints):
            for term in preferred:
                pick = longest_option_containing(options, term)
                if pick:
                    break
            break
    if pick is None and required_answer_missing(obs) and 2 <= len(options) <= 7:
        pick = next(
            (
                option for option in options
                if "not at all" not in option.lower()
                and "never" not in option.lower()
                and not is_progression_cta(option)
                and not is_chrome_option_label(option)
            ),
            None,
        )
    if not pick:
        return None
    if question_select_issued(obs) or teal_radio_filled(obs):
        logger.info("[PREFERENCE ROUTER] Option already issued/filled; not re-tapping %r", pick)
        return None
    node = option_node_for_text(obs, pick)
    kb_key = observation_kb_key(obs) or "inferred_preference"
    if "loyalty" in question:
        kb_key = "loyalty_program_openness"
    logger.info("[PREFERENCE ROUTER] Selecting %r for kb_key=%s", pick, kb_key)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Persona/KB-aligned visible option for this Select-one question: {pick}.",
        "action": "select_option",
        "target_element_id": node.get("id") if node else None,
        "target_text": pick,
        "target_coords": None,
        "input_payload": pick,
        "kb_key": kb_key,
        "kb_write": bool(kb_key in EXACT_KB_QUESTION_HINTS and not obs.kb.get(kb_key)),
        "missing_fact_key": None,
        "confidence_score": 0.86,
        "postcondition": f"selected option is {pick}",
        "visual_reasoning": "Local preference router fills unanswered Select-one from persona/KB before Continue.",
        "answer_provenance": "inferred",
        "source_basis": "persona_data.py tech_adoption/early-adopter policy + visible options",
        "inference_confidence": 0.8,
        "selection_complete": True,
    }
