# 12_maxdiff_selectall.py — shared engine namespace (do not import directly)





_MAXDIFF_SESSION: dict[str, Any] = {"key": "", "most": "", "least": ""}

MAXDIFF_ROW_HINTS = (
    "Availability where I shop", "Softness of the bread", "Calorie content",
    "Occasions it will be used", "Special offer", "Shelf life", "Size of loaf",
    "Healthiness", "Grains in the bread", "Natural/Unprocessed", "Unprocessed",
    "Use by date", "Price", "Brand", "Availability", "Softness", "Calorie",
    "Occasions", "Taste", "Freshness", "Packaging", "Ingredients", "Texture",
    "Quality", "Promotions", "Colour", "Color", "Smell", "Aroma", "Grains",
)
MAXDIFF_PREFERRED_MOST = ("Freshness", "Brand", "Quality", "Taste", "Healthiness", "Price")
MAXDIFF_PREFERRED_LEAST = ("Occasions", "Calorie content", "Calorie", "Availability", "Packaging", "Colour", "Color")


def maxdiff_question_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if "most important" in blob and "least important" in blob:
        return True
    return bool(re.search(r"screen\s+\d+\s+of\s+\d+", blob) and "important" in blob and "least" in blob)


def maxdiff_row_centers(obs: Observation) -> list[tuple[str, int]]:
    blob = str(obs.ocr_text or "")
    labels: list[str] = []
    for hint in MAXDIFF_ROW_HINTS:
        if not re.search(rf"\b{re.escape(hint)}\b", blob, flags=re.I):
            continue
        if any(hint.lower() != other.lower() and hint.lower() in other.lower() for other in labels):
            continue
        labels = [other for other in labels if other.lower() not in hint.lower() or other.lower() == hint.lower()]
        if hint not in labels:
            labels.append(hint)
    height = max(1, int(obs.image_height or 1))
    ranked: list[tuple[str, int]] = []
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        used: list[int] = []
        lines = ocr_line_nodes(Path(obs.screenshot), psm=6)
        for label in labels:
            lab = label.lower()
            hit_y = None
            for node in lines:
                text = node_text(node).lower()
                if lab not in text and text not in lab:
                    continue
                cy = node_center(node)[1]
                yf = cy / height
                if 0.38 <= yf <= 0.88:
                    hit_y = cy
                    break
            if hit_y is None:
                continue
            milli = int(hit_y * 1000 / height)
            if any(abs(milli - prev) < 22 for prev in used):
                continue
            used.append(milli)
            ranked.append((label, milli))
        ranked.sort(key=lambda item: item[1])
        if len(ranked) >= 2:
            return ranked
    if labels:
        start = 500
        step = 55 if len(labels) > 1 else 0
        return [(label, start + index * step) for index, label in enumerate(labels)]
    return [("Price", 510), ("Brand", 565), ("Availability", 620),
            ("Softness", 675), ("Calorie content", 730), ("Occasions", 785)]


def maxdiff_filled(obs: Observation, rows: list[tuple[str, int]]) -> tuple[str, str]:
    most = least = ""
    if not rows or not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return most, least
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            pixels = rgb.load()

            def band(y_milli: int, x0f: float, x1f: float) -> bool:
                y = int(y_milli * height / 1000)
                x0, x1 = int(width * x0f), int(width * x1f)
                hits = 0
                for dy in range(-24, 25, 3):
                    yy = min(height - 1, max(0, y + dy))
                    for x in range(x0, max(x0 + 1, x1), 4):
                        if _lime_pixel(*pixels[min(width - 1, x), yy]):
                            hits += 1
                return hits >= 5

            for label, y_milli in rows:
                if band(y_milli, 0.10, 0.34):
                    most = label
                if band(y_milli, 0.74, 0.97):
                    least = label
    except Exception:
        return most, least
    return most, least


def _maxdiff_pick(candidates: tuple[str, ...], labels: list[str], exclude: str = "") -> str:
    exclude_l = exclude.lower()
    for cand in candidates:
        for label in labels:
            if cand.lower() in label.lower() or label.lower() in cand.lower():
                if exclude_l and (exclude_l in label.lower() or label.lower() in exclude_l):
                    continue
                return label
    for label in labels:
        if exclude_l and (exclude_l in label.lower() or label.lower() in exclude_l):
            continue
        return label
    return labels[-1] if labels else ""


def maxdiff_continue_coords(obs: Observation) -> Optional[tuple[list[int], str]]:
    """Continue only when the green pill or OCR label is in the content band — not the nav bar."""
    height = max(1, int(obs.image_height or 1))
    width = max(1, int(obs.image_width or 1))
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        try:
            with Image.open(obs.screenshot) as image:
                rgb = image.convert("RGB")
                w, h = rgb.size
                pixels = rgb.load()
                best = None
                best_score = 0
                for y in range(int(h * 0.55), int(h * 0.90), 3):
                    xs = [x for x in range(int(w * 0.20), int(w * 0.80), 3) if _lime_pixel(*pixels[x, y])]
                    if len(xs) < 10:
                        continue
                    span = (xs[-1] - xs[0]) / max(1, w)
                    if 0.16 <= span <= 0.50:
                        cx = (xs[0] + xs[-1]) / 2
                        score = len(xs)
                        if score > best_score:
                            best_score = score
                            best = [int(cx * 1000 / w), int(y * 1000 / h)]
                if best and 520 <= best[1] <= 840:
                    logger.info("[MAXDIFF] Green Continue pill at %s", best)
                    return best, "Continue »"
        except Exception as exc:
            logger.debug("[MAXDIFF] pill scan failed: %s", exc)
        for label in ("Continue »", "Continue", "Next »", "Next"):
            hit = ocr_text_center(Path(obs.screenshot), label)
            if not hit:
                continue
            yf = hit[1] / height
            if 0.50 <= yf <= 0.86:
                coords = [
                    int(max(80, min(920, hit[0] * 1000 / width))),
                    int(max(520, min(840, hit[1] * 1000 / height))),
                ]
                return coords, label
    else:
        found = continue_button_on_screen(obs)
        if found and int(found[0][1]) < 850:
            return found
    return None


def maxdiff_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not maxdiff_question_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    page = re.search(r"screen\s+(\d+)\s+of\s+(\d+)", blob)
    page_id = page.group(1) if page else "x"
    key = f"maxdiff-page-{page_id}"
    if _MAXDIFF_SESSION.get("key") != key:
        _MAXDIFF_SESSION.update({"key": key, "most": "", "least": "", "scrolls": 0, "force_scroll": False})
    rows = maxdiff_row_centers(obs)
    labels = [label for label, _ in rows]
    vis_most, vis_least = maxdiff_filled(obs, rows)
    if vis_most:
        _MAXDIFF_SESSION["most"] = vis_most
    if vis_least:
        _MAXDIFF_SESSION["least"] = vis_least
    most = vis_most or str(_MAXDIFF_SESSION.get("most") or "")
    least = vis_least or str(_MAXDIFF_SESSION.get("least") or "")
    logger.info("[MAXDIFF] page=%s rows=%s most=%r least=%r vis=(%r,%r)", page_id, labels, most, least, vis_most, vis_least)
    if most and least and most.lower() != least.lower():
        found = maxdiff_continue_coords(obs)
        scrolls = int(_MAXDIFF_SESSION.get("scrolls") or 0)
        force = bool(_MAXDIFF_SESSION.get("force_scroll"))
        if found and not force:
            coords, label = found
            if int(coords[1]) >= 850:
                found = None
            else:
                logger.info("[MAXDIFF] Most=%s Least=%s; Continue %s at %s", most, least, label, coords)
                return {
                    "screen_state": "survey_question",
                    "question_text": current_question_text(obs),
                    "answer_reason": f"MaxDiff complete (Most={most}, Least={least}); Continue is visible.",
                    "action": "click",
                    "target_element_id": None,
                    "target_text": label,
                    "target_coords": coords,
                    "coordinate_authoritative": True,
                    "confidence_score": 0.96,
                    "postcondition": "screen changed",
                    "selection_complete": True,
                    "maxdiff_done": True,
                }
        if scrolls < 8:
            _MAXDIFF_SESSION["scrolls"] = scrolls + 1
            _MAXDIFF_SESSION["force_scroll"] = False
            logger.info("[MAXDIFF] Both picked; Continue is below the fold — scroll %s/8", scrolls + 1)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": "Most and Least are selected; scroll down to reveal Continue.",
                "action": "scroll_down",
                "target_element_id": None,
                "target_text": None,
                "target_coords": None,
                "confidence_score": 0.97,
                "postcondition": "screen changed",
                "selection_complete": True,
            }
        logger.info("[MAXDIFF] Scroll budget used; tapping lower-content Continue.")
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Scrolled the MaxDiff table; tap Continue in the lower content band.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Continue »",
            "target_coords": [500, 780],
            "coordinate_authoritative": True,
            "confidence_score": 0.9,
            "postcondition": "screen changed",
            "selection_complete": True,
            "maxdiff_done": True,
        }
    if not most:
        pick = _maxdiff_pick(MAXDIFF_PREFERRED_MOST, labels)
        y_milli = next((y for name, y in rows if name == pick), 510)
        logger.info("[MAXDIFF] Tap Most Important on %r at y=%s", pick, y_milli)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"MaxDiff: select Most Important for {pick}.",
            "action": "select_matrix_cell",
            "target_element_id": None,
            "target_text": "Most Important",
            "target_coords": [187, y_milli],
            "coordinate_authoritative": True,
            "row_text": pick,
            "column_text": "Most Important",
            "kb_key": "bread_factor_most",
            "confidence_score": 0.95,
            "postcondition": "maxdiff most selected",
            "selection_complete": False,
            "maxdiff_side": "most",
            "maxdiff_row": pick,
        }
    pick = _maxdiff_pick(MAXDIFF_PREFERRED_LEAST, labels, exclude=most)
    y_milli = next((y for name, y in rows if name == pick), 730)
    logger.info("[MAXDIFF] Tap Least Important on %r at y=%s", pick, y_milli)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"MaxDiff: select Least Important for {pick} (Most already {most}).",
        "action": "select_matrix_cell",
        "target_element_id": None,
        "target_text": "Least Important",
        "target_coords": [870, y_milli],
        "coordinate_authoritative": True,
        "row_text": pick,
        "column_text": "Least Important",
        "kb_key": "bread_factor_least",
        "confidence_score": 0.95,
        "postcondition": "maxdiff least selected",
        "selection_complete": False,
        "maxdiff_side": "least",
        "maxdiff_row": pick,
    }



_SELECT_ALL_SESSION: dict[str, Any] = {"key": "", "done": [], "planned": [], "scrolls": 0}
_SELECT_ONE_SESSION: dict[str, Any] = {"key": "", "taps": 0, "misses": 0, "verified": False}
SELECT_ALL_MIN = 2
SELECT_ALL_HINTS = (
    "Cholesterol lowering", "Low in fat", "High in fibre", "No preservatives",
    "No added sugar", "No additives", "Added nutrients", "No palm oil",
    "Good for your gut", "Low in sugar", "Immune boosting", "Easy to digest",
    "Performance bread", "Made with few ingredients", "High in protein",
    "Other please specify",
)
SELECT_ALL_PREFERRED = (
    "No preservatives", "High in fibre", "Low in fat", "No added sugar",
    "Good for your gut", "High in protein",
)
SELECT_ALL_BRAND_HINTS = (
    "Brennans", "Hovis", "Johnson, Mooney and O'Brien",
    "Johnston, Mooney and O'Brien", "Johnson, Mooney",
)
BRAND_ROW_Y = {
    "hovis": 500,
    "johnson": 580,
    "johnston": 580,
    "mooney": 580,
    "brennans": 660,
}


def select_all_is_brand_bought(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return "brand" in blob and ("ever bought" in blob or "have you ever bought" in blob)


def select_all_min_required(ocr_text: str) -> int:
    match = re.search(r"at least\s+(\d+)", str(ocr_text or "").lower())
    if match:
        return max(1, int(match.group(1)))
    return 1 if select_all_is_brand_bought(ocr_text) else SELECT_ALL_MIN


def select_all_session_key(obs: Observation) -> str:
    if select_all_is_brand_bought(obs.ocr_text):
        return "select-all-brands-bought"
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if "claims" in blob:
        return "select-all-claims"
    return "select-all-" + question_fingerprint(obs)[:24]


def select_all_apply_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if "select all that apply" in blob or "choose all that apply" in blob:
        return True
    if "claims" in blob and "important" in blob and "bread" in blob:
        return True
    return False


def select_all_brand_token(name: str) -> str:
    low = str(name or "").lower()
    if "brennan" in low:
        return "brennans"
    if "hovis" in low:
        return "hovis"
    if "johnson" in low or "johnston" in low or "mooney" in low:
        return "johnson"
    return re.sub(r"[^a-z]+", "", low)[:16]


def select_all_dedupe_brands(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        token = select_all_brand_token(name)
        if not token or token in seen:
            continue
        if token in {"none", "others", "specify"}:
            continue
        seen.add(token)
        out.append(name)
    return out


def select_all_brand_y(name: str, miss: int = 0) -> int:
    token = select_all_brand_token(name)
    base = BRAND_ROW_Y.get(token, 580)
    ladder = [base, 580, 660, 500, 620, 700]
    return ladder[int(miss) % len(ladder)]


def select_all_row_centers(obs: Observation) -> list[tuple[str, int]]:
    blob = str(obs.ocr_text or "")
    brand = select_all_is_brand_bought(blob)
    hints = SELECT_ALL_BRAND_HINTS if brand else SELECT_ALL_HINTS
    labels: list[str] = []
    for hint in hints:
        if re.search(r"other|specify|none of these", hint, flags=re.I):
            continue
        if not re.search(re.escape(hint.split(",")[0]), blob, flags=re.I) and not re.search(re.escape(hint), blob, flags=re.I):
            if brand and not re.search(select_all_brand_token(hint), blob, flags=re.I):
                continue
            if not brand:
                continue
        if hint not in labels:
            labels.append(hint)
    if brand:
        labels = select_all_dedupe_brands(labels or ["Brennans", "Johnson, Mooney and O'Brien"])
    height = max(1, int(obs.image_height or 1))
    ranked: list[tuple[str, int]] = []
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        lines = ocr_line_nodes(Path(obs.screenshot), psm=6)
        used: list[int] = []
        for label in labels:
            tokens = [t for t in re.split(r"[^a-z]+", label.lower()) if len(t) >= 4]
            hit_y = None
            for node in lines:
                text = node_text(node).lower()
                if not tokens or not any(token in text for token in tokens):
                    continue
                cy = node_center(node)[1]
                if 0.42 <= (cy / height) <= 0.88:
                    hit_y = cy
                    break
            if hit_y is None:
                continue
            milli = int(hit_y * 1000 / height)
            if milli < 450:
                continue
            if any(abs(milli - prev) < 28 for prev in used):
                continue
            used.append(milli)
            ranked.append((label, milli))
        ranked.sort(key=lambda item: item[1])
        if ranked:
            return ranked
    if brand:
        return [(label, select_all_brand_y(label)) for label in labels] or [
            ("Johnson, Mooney and O'Brien", 580),
            ("Brennans", 660),
        ]
    if labels:
        start = 450
        step = 90
        return [(label, start + index * step) for index, label in enumerate(labels)]
    return [(label, 450 + index * 90) for index, label in enumerate(SELECT_ALL_PREFERRED[:4])]


def select_all_green_labels(obs: Observation, rows: list[tuple[str, int]]) -> list[str]:
    filled: list[str] = []
    if not rows or not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return list(_SELECT_ALL_SESSION.get("done") or [])
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            pixels = rgb.load()
            x0, x1 = int(width * 0.08), int(width * 0.92)
            for label, y_milli in rows:
                y = int(y_milli * height / 1000)
                hits = samples = 0
                for dy in range(-18, 19, 3):
                    yy = min(height - 1, max(0, y + dy))
                    for x in range(x0, x1, 6):
                        samples += 1
                        if _lime_pixel(*pixels[x, yy]):
                            hits += 1
                if samples and hits / samples >= 0.08:
                    filled.append(label)
    except Exception:
        return list(_SELECT_ALL_SESSION.get("done") or [])
    return filled


def select_all_lime_band_count(obs: Observation) -> int:
    """Count distinct lime-green checkbox rows on the screenshot."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return 0
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            pixels = rgb.load()
            x0, x1 = int(width * 0.10), int(width * 0.72)
            y0, y1 = int(height * 0.44), int(height * 0.72)
            bands = 0
            in_band = False
            gap = 0
            for y in range(y0, y1, 6):
                hits = samples = 0
                for x in range(x0, x1, 8):
                    samples += 1
                    if _lime_pixel(*pixels[x, y]):
                        hits += 1
                lime = samples and hits / samples >= 0.10
                if lime:
                    if not in_band:
                        bands += 1
                        in_band = True
                    gap = 0
                else:
                    gap += 1
                    if gap >= 3:
                        in_band = False
            return bands
    except Exception:
        return 0


def select_all_apply_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not select_all_apply_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    key = select_all_session_key(obs)
    if _SELECT_ALL_SESSION.get("key") != key:
        _SELECT_ALL_SESSION.update({"key": key, "done": [], "planned": [], "scrolls": 0, "misses": 0})
    rows = select_all_row_centers(obs)
    labels = [name for name, _ in rows]
    planned = list(_SELECT_ALL_SESSION.get("planned") or [])
    if not planned:
        if select_all_is_brand_bought(obs.ocr_text):
            ranked_plan: list[str] = []
            for lab in labels:
                token = select_all_brand_token(lab)
                if token == "brennans":
                    ranked_plan.insert(0, lab)
                elif token == "johnson":
                    ranked_plan.append(lab)
            planned = select_all_dedupe_brands(ranked_plan or labels)[:2]
            if not planned:
                planned = ["Brennans", "Johnson, Mooney and O'Brien"]
        else:
            planned = [name for name in SELECT_ALL_PREFERRED if any(name.lower() in lab.lower() or lab.lower() in name.lower() for lab in labels)]
            if len(planned) < SELECT_ALL_MIN:
                for lab in labels:
                    if lab not in planned:
                        planned.append(lab)
                    if len(planned) >= SELECT_ALL_MIN:
                        break
            planned = planned[: max(SELECT_ALL_MIN, min(3, len(planned) or SELECT_ALL_MIN))]
            if not planned:
                planned = list(SELECT_ALL_PREFERRED[:SELECT_ALL_MIN])
        _SELECT_ALL_SESSION["planned"] = planned
        logger.info("[SELECT ALL] Plan tick %s then Continue.", planned)
    visual = select_all_green_labels(obs, rows)
    bands = select_all_lime_band_count(obs)
    ocr_zero = bool(re.search(r"(?i)you selected\s*0\b", str(obs.ocr_text or "")))
    selected_zero = ocr_zero and not visual and bands < 1
    done = []
    for name in list(visual) + list(_SELECT_ALL_SESSION.get("done") or []):
        if name not in done:
            done.append(name)
    if bands >= 1 and not done:
        done = ["lime-row"] * min(bands, 3)
    _SELECT_ALL_SESSION["done"] = [n for n in done if n != "lime-row"] or done
    remaining = [name for name in planned if not any(name.lower() in d.lower() or d.lower() in name.lower() for d in done)]
    logger.info("[SELECT ALL] planned=%s done=%s remaining=%s lime_bands=%s", planned, done, remaining, bands)
    need = select_all_min_required(obs.ocr_text)
    complete = (bands >= need) or (len([d for d in done if d != "lime-row"]) >= need) or (bands >= 1 and need <= 1)
    if complete and not selected_zero:
        found = maxdiff_continue_coords(obs)
        if not found:
            found = continue_button_on_screen(obs)
        coords = None
        label = "Continue »"
        if found:
            coords = found[0]
            label = found[1] if len(found) > 1 else "Continue »"
        if coords and int(coords[1]) < 850:
            logger.info("[SELECT ALL] %s ticked; Continue at %s", done, coords)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": f"Select-all complete ({done}); Continue is visible.",
                "action": "click",
                "target_element_id": None,
                "target_text": label,
                "target_coords": coords,
                "coordinate_authoritative": True,
                "confidence_score": 0.96,
                "postcondition": "screen changed",
                "selection_complete": True,
                "select_all_done": True,
                "kb_key": "bread_claims",
            }
        scrolls = int(_SELECT_ALL_SESSION.get("scrolls") or 0)
        if scrolls < 8:
            _SELECT_ALL_SESSION["scrolls"] = scrolls + 1
            logger.info("[SELECT ALL] %s ticked; scroll for Continue %s/8", done, scrolls + 1)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": "Two claims are ticked; scroll down to Continue.",
                "action": "scroll_down",
                "target_element_id": None,
                "target_text": None,
                "target_coords": None,
                "confidence_score": 0.97,
                "postcondition": "screen changed",
                "selection_complete": True,
            }
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Select-all filled; tap lower Continue.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Continue »",
            "target_coords": [500, 780],
            "coordinate_authoritative": True,
            "confidence_score": 0.9,
            "postcondition": "screen changed",
            "select_all_done": True,
        }
    if not remaining:
        remaining = [
            lab for lab in (planned or labels)
            if not any(lab.lower() in str(d).lower() for d in done)
            and not re.search(r"none of these|specify", str(lab).lower())
        ]
        if not remaining and labels:
            remaining = [labels[0]]
        if not remaining:
            remaining = ["Brennans"] if select_all_is_brand_bought(obs.ocr_text) else list(SELECT_ALL_PREFERRED[:1])
    pick = remaining[0]
    miss = int(_SELECT_ALL_SESSION.get("misses") or 0)
    y_milli = next((y for name, y in rows if name == pick), None)
    if y_milli is None or int(y_milli) < 450:
        y_milli = select_all_brand_y(pick, miss) if select_all_is_brand_bought(obs.ocr_text) else 520
    if selected_zero:
        _SELECT_ALL_SESSION["misses"] = miss + 1
        y_milli = select_all_brand_y(pick, miss)
    tap_x = 200 if select_all_is_brand_bought(obs.ocr_text) else 500
    logger.info("[SELECT ALL] Tick %r at [%s,%s] miss=%s", pick, tap_x, y_milli, miss)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Select-all plan: tick {pick} ({len(done)+1}/{need}).",
        "action": "select_option",
        "target_element_id": None,
        "target_text": pick,
        "target_coords": [tap_x, y_milli],
        "coordinate_authoritative": True,
        "kb_key": "bread_brands_bought" if select_all_is_brand_bought(obs.ocr_text) else "bread_claims",
        "kb_write": False,
        "confidence_score": 0.95,
        "postcondition": "selected option is " + pick,
        "selection_complete": False,
        "select_all_pick": pick,
        "intended_options": planned,
    }


_HEARD_SESSION: dict[str, Any] = {"key": "", "n": 0, "ticked": []}
AI_HEARD_HINTS = (
    "ChatGPT", "Gemini", "Copilot", "Siri", "Alexa", "Google Assistant",
    "Bixby", "Claude", "Perplexity", "Meta AI", "Apple Intelligence",
)
AI_HEARD_PREFERRED = ("ChatGPT", "Gemini", "Google Assistant", "Copilot")


def heard_of_assistants_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if "have you heard of" in text:
        return True
    return "which of the following" in text and (
        "ai assistant" in text or "chatbot" in text or "artificial intelligence" in text
    )


def heard_of_option_labels(ocr_text: str) -> list[str]:
    blob = str(ocr_text or "")
    found: list[str] = []
    for name in AI_HEARD_HINTS:
        if re.search(rf"\b{re.escape(name)}\b", blob, re.I):
            found.append(name)
    return found


def heard_of_arrow_milli(obs: Observation) -> list[int]:
    for name in ("purple_submit_arrow_milli", "mapped_age_arrow_milli", "smartphone_continue_milli"):
        fn = globals().get(name)
        if not callable(fn):
            continue
        hit = fn(obs)
        if hit and 520 <= int(hit[1]) <= 920:
            return [int(hit[0]), int(hit[1])]
    return [500, 860]


def heard_of_assistants_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Intro + 'have you heard of' with choices below: scroll, tick known AIs, then purple arrow."""
    if not heard_of_assistants_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    key = question_fingerprint(obs)
    if _HEARD_SESSION.get("key") != key:
        _HEARD_SESSION.update({"key": key, "n": 0, "ticked": []})
    labels = heard_of_option_labels(obs.ocr_text)
    arrow = heard_of_arrow_milli(obs)
    if not labels:
        n = int(_HEARD_SESSION.get("n") or 0)
        if n < 6:
            _HEARD_SESSION["n"] = n + 1
            logger.info("[HEARD OF] Choices are below the intro; scroll webview %s/6", n + 1)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": "AI-assistant choices are below the intro; scroll the page, then tick, then the purple arrow.",
                "action": "scroll_down", "list_scroll": True,
                "target_element_id": None, "target_text": None, "target_coords": None,
                "confidence_score": 0.96, "postcondition": "screen changed",
                "skip_object_grounding": True,
            }
        logger.info("[HEARD OF] Scroll budget used; purple arrow %s", arrow)
        return {
            "screen_state": "survey_question", "action": "click", "target_text": "Continue",
            "target_coords": arrow, "coordinate_authoritative": True,
            "confidence_score": 0.9, "postcondition": "screen changed",
            "answer_reason": "No choice labels after scrolling; tap the purple arrow.",
            "skip_object_grounding": True, "object_kind": "button",
        }
    ticked = list(_HEARD_SESSION.get("ticked") or [])
    planned = [name for name in AI_HEARD_PREFERRED if any(name.lower() in lab.lower() for lab in labels)] or labels[:3]
    remaining = [name for name in planned if name.lower() not in {t.lower() for t in ticked}]
    if remaining:
        pick = remaining[0]
        row = None
        if "select_one_ocr_row_milli" in globals():
            row = select_one_ocr_row_milli(obs, pick)
        tap = [int(row[0]), int(row[1])] if row else [500, 520]
        _HEARD_SESSION["ticked"] = ticked + [pick]
        payload = ", ".join(_HEARD_SESSION["ticked"])
        logger.info("[HEARD OF] Tick %r at %s then more/arrow", pick, tap)
        return {
            "screen_state": "survey_question", "action": "select_option",
            "target_text": pick, "target_coords": tap, "coordinate_authoritative": True,
            "input_payload": payload, "kb_key": "ai_assistants_heard", "kb_write": True,
            "confidence_score": 0.95, "postcondition": "selected option is " + pick,
            "answer_reason": f"Persona uses {pick}; tick it (select-all), then the purple arrow.",
            "answer_provenance": "declared",
            "source_basis": "persona tech_adoption / knowledge_base.json:ai_assistants_heard",
        }
    logger.info("[HEARD OF] Ticked %s; purple arrow %s", ticked, arrow)
    return {
        "screen_state": "survey_question", "action": "click", "target_text": "Continue",
        "target_coords": arrow, "coordinate_authoritative": True,
        "input_payload": ", ".join(ticked), "kb_key": "ai_assistants_heard", "kb_write": True,
        "confidence_score": 0.96, "postcondition": "screen changed",
        "answer_reason": "Heard-of choices are ticked; tap the purple arrow (not the intro text).",
        "skip_object_grounding": True, "object_kind": "button",
    }
