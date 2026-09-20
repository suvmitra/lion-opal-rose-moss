# 11_carousel.py — shared engine namespace (do not import directly)



_CAROUSEL_SESSION: dict[str, Any] = {
    "item": "",
    "answered": False,
    "done": [],
    "right_stagnant": 0,
}

CAROUSEL_CHOICE_LABELS = (
    "About the same",
    "More often",
    "Less often",
    "Much more often",
    "A little more often",
    "A little less often",
    "Much less often",
    "I don't buy this type of bread",
    "Don't know / can't remember",
)

CAROUSEL_KNOWN_ITEMS = (
    "Bagels", "Baps", "Rolls", "Buns", "Ciabatta", "Sourdough", "Wholemeal",
    "White bread", "Brown bread", "Pitta", "Pita", "Naan", "Wraps", "Tortilla",
    "Baguette", "Croissant", "Brioche", "Soda bread", "Panini", "Focaccia",
    "Sliced Bread", "Batch", "Tiger bread", "Granary",
)

CAROUSEL_SKIP_NEEDLES = (
    "survey", "continue", "select one", "please select", "please follow",
    "change in the types", "types of bread bought", "accessibility",
    "more often", "about the same", "less often", "don't buy", "do not buy",
    "don't know", "cant remember", "can't remember", "there were problems",
    "errors below", "instructions attached", "questions with errors",
    "data you entered", "follow the", "help",
    "thanks for those", "please click continue", "next question",
)


def carousel_row_question_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return any(term in blob for term in (
        "select one in each row",
        "one in each row",
        "change in the types of bread",
        "types of bread bought",
    ))


def carousel_skip_label(label: str) -> bool:
    low = re.sub(r"\s+", " ", str(label or "").strip().lower())
    if not low or len(low) > 40:
        return True
    return any(needle in low for needle in CAROUSEL_SKIP_NEEDLES)


def carousel_item_valid(label: str) -> bool:
    text = re.sub(r"\s+", " ", str(label or "").strip())
    if not text or carousel_skip_label(text):
        return False
    if is_progression_cta(text):
        return False
    words = text.split()
    return 1 <= len(words) <= 4 and 2 <= len(text) <= 32


def _lime_pixel(r: int, g: int, b: int) -> bool:
    return g >= 140 and g > r + 20 and g > b + 10 and r >= 60 and b < 170


def carousel_current_item(obs: Observation) -> str:
    blob = str(obs.ocr_text or "")
    for name in CAROUSEL_KNOWN_ITEMS:
        if re.search(rf"\b{re.escape(name)}\b", blob, flags=re.I):
            return name
    height = max(1, int(obs.image_height or 1))
    width = max(1, int(obs.image_width or 1))
    banner = "problems with some of the data" in blob.lower()
    y0, y1 = (0.40, 0.58) if banner else (0.24, 0.42)
    ranked: list[tuple[float, str]] = []
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        for psm in (6, 11):
            for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                label = re.sub(r"\s+", " ", node_text(node)).strip()
                if not carousel_item_valid(label):
                    continue
                cx, cy = node_center(node)
                xf, yf = cx / width, cy / height
                if 0.28 <= xf <= 0.72 and y0 <= yf <= y1:
                    ranked.append((abs(xf - 0.5) + abs(yf - ((y0 + y1) / 2)), label))
    if ranked:
        ranked.sort()
        return ranked[0][1]
    for raw in blob.splitlines():
        label = re.sub(r"\s+", " ", raw).strip()
        if carousel_item_valid(label) and label[0].isupper():
            return label
    remembered = str(_CAROUSEL_SESSION.get("item") or "").strip()
    return remembered if carousel_item_valid(remembered) else ""


def _option_gray_pixel(r: int, g: int, b: int) -> bool:
    return abs(r - g) < 22 and abs(g - b) < 22 and 150 <= int((r + g + b) / 3) <= 220


def carousel_gray_tiles(obs: Observation) -> list[list[int]]:
    """Milli centers of the wide gray option bars below the carousel title."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return []
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            pixels = rgb.load()
            banner = "problems with some of the data" in (obs.ocr_text or "").lower()
            y0 = int(height * (0.52 if banner else 0.40))
            y1 = int(height * 0.88)
            x0, x1 = int(width * 0.08), int(width * 0.92)
            flags = []
            for y in range(y0, y1, 2):
                gray = samples = 0
                for x in range(x0, x1, 4):
                    samples += 1
                    if _option_gray_pixel(*pixels[x, y]):
                        gray += 1
                flags.append((y, bool(samples and gray / samples >= 0.52)))
            tiles = []
            run_y = []
            min_h = int(height * 0.035)
            max_h = int(height * 0.14)
            for y, on in flags + [(y1, False)]:
                if on:
                    run_y.append(y)
                    continue
                if run_y and min_h <= (run_y[-1] - run_y[0]) <= max_h:
                    cy = (run_y[0] + run_y[-1]) / 2
                    tiles.append([500, int(max(480, min(860, cy * 1000 / height)))])
                run_y = []
            logger.info("[CAROUSEL] Gray option tiles=%s", tiles)
            return tiles
    except Exception as exc:
        logger.warning("[CAROUSEL] Gray-tile scan failed: %s", exc)
        return []


def carousel_choice_coords(obs: Observation, wanted: str = "About the same") -> list[int]:
    height = max(1, int(obs.image_height or 1))
    banner = "problems with some of the data" in (obs.ocr_text or "").lower()
    floor = 620 if banner else 500
    item_y = carousel_item_milli_y(obs)
    tiles = carousel_gray_tiles(obs)
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        hit = ocr_text_center(Path(obs.screenshot), wanted)
        if hit:
            milli_y = int(hit[1] * 1000 / height)
            if milli_y >= max(floor, item_y + 90) and milli_y <= 860:
                logger.info("[CAROUSEL] OCR %r at milli-y=%s", wanted, milli_y)
                return [500, milli_y]
    if tiles:
        try_n = int(_CAROUSEL_SESSION.get("tap_try") or 0)
        if try_n == 0 and len(tiles) >= 2:
            idx = 1
        else:
            idx = try_n % len(tiles)
        coords = tiles[idx]
        logger.info("[CAROUSEL] Using gray tile %s/%s coords=%s try=%s", idx + 1, len(tiles), coords, try_n)
        return coords
    return [500, 720 if banner else 560]


def carousel_thanks_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return (
        "thanks for those answers" in blob
        or ("please click continue" in blob and "next question" in blob)
    )


def carousel_item_milli_y(obs: Observation) -> int:
    item = carousel_current_item(obs)
    height = max(1, int(obs.image_height or 1))
    blob = (obs.ocr_text or "").lower()
    banner = any(term in blob for term in (
        "problems with some of the data", "please select an answer", "questions with errors",
    ))
    thanks = carousel_thanks_visible(obs.ocr_text)
    floor = 0.42 if (banner or thanks) else 0.22
    if thanks and obs.screenshot and Path(str(obs.screenshot)).exists():
        hit = ocr_text_center(Path(obs.screenshot), "Thanks for those answers") or ocr_text_center(
            Path(obs.screenshot), "please click continue"
        )
        if hit:
            yf = hit[1] / height
            if 0.40 <= yf <= 0.70:
                return int(max(480, min(620, hit[1] * 1000 / height)))
    if item and obs.screenshot and Path(str(obs.screenshot)).exists():
        hit = ocr_text_center(Path(obs.screenshot), item)
        if hit:
            yf = hit[1] / height
            if floor <= yf <= 0.62:
                return int(max(460 if banner else 280, min(560, hit[1] * 1000 / height)))
    if thanks:
        return 520
    return 500 if banner else 330


def carousel_right_arrow_coords(obs: Observation) -> list[int]:
    return [900, carousel_item_milli_y(obs)]


def carousel_left_arrow_coords(obs: Observation) -> list[int]:
    return [100, carousel_item_milli_y(obs)]


def carousel_progress_fraction(obs: Observation) -> float:
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return 0.0
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            pixels = rgb.load()
            best = 0.0
            x0, x1 = int(width * 0.08), int(width * 0.92)
            for y in range(int(height * 0.28), int(height * 0.62), 2):
                lime = gray = 0
                for x in range(x0, x1, 3):
                    r, g, b = pixels[x, y]
                    if _lime_pixel(r, g, b):
                        lime += 1
                    elif abs(r - g) < 20 and abs(g - b) < 20 and 150 <= r <= 230:
                        gray += 1
                total = lime + gray
                if total >= 12:
                    best = max(best, lime / max(1, total))
            return best
    except Exception:
        return 0.0


def carousel_has_green_selection(obs: Observation) -> bool:
    """True only for a WIDE, TALL green option tile — not the progress bar or Continue pill."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        item = carousel_current_item(obs)
        return bool(_CAROUSEL_SESSION.get("answered")) and str(_CAROUSEL_SESSION.get("item") or "").lower() == item.lower()
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            pixels = rgb.load()
            x0, x1 = int(width * 0.08), int(width * 0.92)
            min_h = int(height * 0.035)
            run = 0
            for y in range(int(height * 0.56), int(height * 0.88), 2):
                lime = samples = 0
                for x in range(x0, x1, 4):
                    samples += 1
                    if _lime_pixel(*pixels[x, y]):
                        lime += 1
                if samples and lime / samples >= 0.45:
                    run += 2
                    if run >= min_h:
                        return True
                else:
                    run = 0
    except Exception:
        return False
    return False


def green_continue_pill_coords(obs: Observation) -> Optional[list[int]]:
    """Milli center of the compact lime Continue pill."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return None
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            pixels = rgb.load()
            best = None
            best_score = 0
            for y in range(int(height * 0.48), int(height * 0.84), 3):
                xs = [x for x in range(int(width * 0.20), int(width * 0.80), 3) if _lime_pixel(*pixels[x, y])]
                if len(xs) < 8:
                    continue
                span = (xs[-1] - xs[0]) / max(1, width)
                if 0.14 <= span <= 0.48:
                    cx = (xs[0] + xs[-1]) / 2
                    score = len(xs)
                    if score > best_score:
                        best_score = score
                        best = [int(cx * 1000 / width), int(y * 1000 / height)]
            if best and 480 <= best[1] <= 860:
                logger.info("[CAROUSEL] Green Continue pill at %s", best)
                return best
    except Exception as exc:
        logger.debug("[CAROUSEL] Continue-pill scan failed: %s", exc)
    return None


def carousel_right_arrow_enabled(obs: Observation) -> bool:
    coords = carousel_right_arrow_coords(obs)
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return True
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            x = int(min(width - 6, max(4, coords[0] * width / 1000)))
            y = int(min(height - 6, max(4, coords[1] * height / 1000)))
            pixels = rgb.load()
            samples = []
            for dx in (-12, -4, 0, 4, 12):
                for dy in (-12, -4, 0, 4, 12):
                    samples.append(pixels[min(width - 1, max(0, x + dx)), min(height - 1, max(0, y + dy))])
            brightness = sum(sum(px) / 3 for px in samples) / max(1, len(samples))
            enabled = brightness < 150
            logger.info("[CAROUSEL] Right-arrow brightness=%.0f enabled=%s at %s", brightness, enabled, coords)
            return enabled
    except Exception:
        return True


def carousel_complete(obs: Observation) -> bool:
    if carousel_thanks_visible(obs.ocr_text):
        return True
    progress = carousel_progress_fraction(obs)
    selected = carousel_has_green_selection(obs)
    stagnant = int(_CAROUSEL_SESSION.get("right_stagnant") or 0)
    right_on = carousel_right_arrow_enabled(obs)
    if obs.screenshot is None and stagnant >= 2 and selected:
        return True
    if not selected:
        return False
    if progress >= 0.82:
        return True
    if not right_on:
        return True
    if stagnant >= 2 and not right_on:
        return True
    return False


def carousel_continue_click(obs: Observation, reason: str) -> dict[str, Any]:
    pill = green_continue_pill_coords(obs)
    found = continue_button_on_screen(obs)
    if pill:
        coords, label = pill, "Continue »"
    elif found:
        coords, label = found
    else:
        coords, label = [500, 680], "Continue »"
    logger.info("[CAROUSEL] Continue because %s coords=%s", reason, coords)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": reason,
        "action": "click",
        "target_element_id": None,
        "target_text": label,
        "target_coords": coords,
        "coordinate_authoritative": True,
        "confidence_score": 0.95,
        "postcondition": "screen changed",
        "selection_complete": True,
    }


def carousel_row_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not carousel_row_question_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    item = carousel_current_item(obs) or "current row"
    selected = carousel_has_green_selection(obs)
    tiles = carousel_gray_tiles(obs) if obs.screenshot else []
    thanks = carousel_thanks_visible(obs.ocr_text)
    progress = carousel_progress_fraction(obs)
    left_reviews = int(_CAROUSEL_SESSION.get("left_reviews") or 0)
    logger.info(
        "[CAROUSEL] item=%r selected=%s progress=%.2f thanks=%s tiles=%s left=%s stagnant=%s",
        item, selected, progress, thanks, len(tiles), left_reviews,
        _CAROUSEL_SESSION.get("right_stagnant"),
    )
    if thanks:
        if tiles and not selected:
            wanted = "About the same"
            coords = tiles[1] if len(tiles) >= 2 else tiles[0]
            logger.info("[CAROUSEL] Thanks card still has gray tiles; tap %s at %s", wanted, coords)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": "End card still shows unanswered gray tiles; fill them before Continue.",
                "action": "select_option",
                "target_element_id": None,
                "target_text": wanted,
                "target_coords": coords,
                "coordinate_authoritative": True,
                "input_payload": wanted,
                "confidence_score": 0.9,
                "postcondition": f"selected option is {wanted}",
                "selection_complete": False,
                "carousel_item": item,
            }
        # Leftover Qualtrics banner is normal on this card. The on-screen
        # instruction is to click Continue. Only step left when gray rows exist
        # (handled above). A miss-aimed left chevron caused 4-cycle stagnation.
        return carousel_continue_click(
            obs, "Thanks for those answers — click the green Continue button.",
        )
    if tiles and not selected:
        wanted = "About the same"
        coords = carousel_choice_coords(obs, wanted)
        kb_key = None
        kb_write = False
        if item and item != "current row":
            kb_key = f"bread_bought_{re.sub(r'[^a-z0-9]+', '_', item.lower()).strip('_')}"
            kb_write = True
        logger.info("[CAROUSEL] Answer %r with %r coords=%s", item, wanted, coords)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Carousel row {item} is unanswered; tap {wanted}, then the right arrow.",
            "action": "select_option",
            "target_element_id": None,
            "target_text": wanted,
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": wanted,
            "kb_key": kb_key,
            "kb_write": kb_write,
            "confidence_score": 0.94,
            "postcondition": f"selected option is {wanted}",
            "answer_provenance": "inferred",
            "source_basis": "Default mid-scale for each carousel row",
            "selection_complete": False,
            "carousel_item": item,
        }
    if not selected:
        wanted = "About the same"
        coords = carousel_choice_coords(obs, wanted)
        logger.info("[CAROUSEL] No green tile; tap %r at %s", wanted, coords)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Carousel row {item} is unanswered; tap {wanted}, then the right arrow.",
            "action": "select_option",
            "target_element_id": None,
            "target_text": wanted,
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": wanted,
            "confidence_score": 0.9,
            "postcondition": f"selected option is {wanted}",
            "selection_complete": False,
            "carousel_item": item,
        }
    if not carousel_complete(obs):
        coords = carousel_right_arrow_coords(obs)
        logger.info("[CAROUSEL] %r selected; tap right arrow coords=%s progress=%.2f", item, coords, progress)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"{item} is answered; progress {progress:.0%} — tap the right arrow, not Continue.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Next row",
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": item,
            "kb_key": None,
            "kb_write": False,
            "confidence_score": 0.96,
            "postcondition": "screen changed",
            "selection_complete": False,
            "carousel_advance": True,
            "carousel_item": item,
        }
    return carousel_continue_click(obs, f"Carousel finished on {item}; Continue.")
