# 20_text_fields.py — shared engine namespace (do not import directly)



def visual_text_field_coords(obs: Observation) -> list[int]:
    """Locate a WebView underline-style text field; return normalized tap coords."""
    fallback = [500, 750]
    if not obs.screenshot or not Path(obs.screenshot).exists():
        return fallback
    try:
        with Image.open(obs.screenshot) as source:
            image = source.convert("RGB")
            width, height = image.size
            scaled_width = 280
            scaled_height = max(1, int(height * scaled_width / max(1, width)))
            image = image.resize((scaled_width, scaled_height), Image.Resampling.BILINEAR)
            pixels = image.load()
            candidates: list[tuple[float, int]] = []
            for y in range(int(scaled_height * 0.45), int(scaled_height * 0.84)):
                neutral = 0
                for x in range(image.width):
                    red, green, blue = pixels[x, y]
                    if (
                        max(red, green, blue) - min(red, green, blue) <= 10
                        and 165 <= red <= 242
                    ):
                        neutral += 1
                coverage = neutral / max(1, image.width)
                if coverage >= 0.42:
                    relative_y = y / max(1, scaled_height)
                    score = coverage - abs(relative_y - 0.78) * 0.8
                    candidates.append((score, y))
            if candidates:
                _, line_y = max(candidates)
                tap_y = max(0, line_y - int(scaled_height * 0.035))
                return [500, int(max(0, min(1000, tap_y * 1000 / scaled_height)))]
    except Exception as exc:
        logger.debug("Visual text-field grounding unavailable: %s", exc)
    return fallback


TEXT_KB_QUESTION_HINTS: dict[str, tuple[str, ...]] = {
    "child_age": ("state their ages", "their ages", "child's age", "whole number"),
    "age": ("what is your age", "how old are you", "your age"),
    "full_name": ("full name", "your name", "first and last name"),
    "email": ("email address", "your email", "e-mail"),
    "phone": ("phone number", "mobile number", "telephone"),
    "city": ("what city", "which city", "city do you live"),
    "postal_code": ("postcode", "postal code", "zip code", "eircode"),
    "area_code": ("routing key", "a96", "for ie"),
    "bread_brands_aware": ("brands of bread", "brands of breads", "bread brands", "aware of"),
}

PERSONAL_FACT_KEYS = {
    "age", "full_name", "email", "phone", "city", "postal_code", "area_code",
    "gender", "household_pets", "smoking_status", "employment_status",
    "marital_status", "has_children", "number_of_children", "child_age",
    "child_gender", "education",
    "industry", "housing", "nationality_residency",
    "bread_brands_aware",
}


def nested_scalar(container: Any, key: str) -> Any:
    if not isinstance(container, dict):
        return None
    if container.get(key) not in (None, ""):
        return container.get(key)
    for value in container.values():
        found = nested_scalar(value, key)
        if found not in (None, ""):
            return found
    return None


def resolve_text_kb_key(question: str) -> Optional[str]:
    q = re.sub(r"\s+", " ", str(question or "").lower())
    if child_ages_question_visible(q):
        return "child_age"
    if "age" in q and any(term in q for term in ("what is your age", "how old", "enter a number", "your age")):
        return "age"
    if any(term in q for term in ("postcode", "postal code", "eircode", "zip code")):
        if any(term in q for term in ("a96", "for ie", "routing key")):
            return "area_code"
        return "postal_code"
    for key, hints in TEXT_KB_QUESTION_HINTS.items():
        if any(hint in q for hint in hints):
            return key
    return None


def kb_or_persona_value(obs: Observation, kb_key: str) -> Any:
    value = (obs.kb or {}).get(kb_key)
    if value not in (None, ""):
        return value
    if kb_key == "child_age":
        resolved = resolve_child_age_value(obs)
        if resolved not in (None, ""):
            return resolved
    if kb_key == "area_code":
        full_code = str((obs.kb or {}).get("postal_code") or "").replace(" ", "")
        match = re.match(r"[A-Za-z]\d{2}", full_code)
        if match:
            return match.group(0).upper()
    return nested_scalar(obs.persona, kb_key)


def coerce_tap_coords(coords: Any, image_size: tuple[int, int]) -> Optional[list[int]]:
    """Accept [x,y] or a 4-number box; return normalized 0..1000 center."""
    if not isinstance(coords, (list, tuple)) or len(coords) not in {2, 4}:
        return None
    try:
        nums = [float(item) for item in coords]
    except (TypeError, ValueError):
        return None
    if len(nums) == 4:
        nums = [(nums[0] + nums[2]) / 2.0, (nums[1] + nums[3]) / 2.0]
    x, y = nums
    iw, ih = image_size
    if max(x, y) > 1000 and iw and ih:
        x = x * 1000.0 / max(1, iw)
        y = y * 1000.0 / max(1, ih)
    return [
        int(max(0, min(1000, round(x)))),
        int(max(0, min(1000, round(y)))),
    ]


def looks_like_typed_value(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    lowered = value.lower()
    if is_progression_cta(value) or is_forbidden_progression_target(value):
        return False
    if lowered in OPTION_CHROME_LABELS or lowered in {
        "postcode input field", "input field", "text field", "age", "your age",
        "enter a number", "what is your age?",
    }:
        return False
    if "?" in value:
        return False
    if re.fullmatch(r"\d{1,3}", value):
        return True
    return 1 <= len(value) <= 48


def clickable_empty_field_node(obs: Observation) -> Optional[dict[str, Any]]:
    """WebView often exposes the input as an unlabeled clickable, not editable=true."""
    best = None
    best_score = -1.0
    for node in obs.ui_nodes:
        if not node.get("enabled"):
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in bounds]
        width, height = x2 - x1, y2 - y1
        if width <= 0 or height <= 0:
            continue
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        label = node_text(node).strip()
        if label and is_progression_cta(label):
            continue
        if label and is_forbidden_progression_target(label):
            continue
        if not (obs.image_height * 0.18 <= cy <= obs.image_height * 0.52):
            continue
        if cx > obs.image_width * 0.50:
            continue
        if width < obs.image_width * 0.12 or width > obs.image_width * 0.60:
            continue
        if height < obs.image_height * 0.018 or height > obs.image_height * 0.12:
            continue
        if not (node.get("editable") or node.get("clickable") or node.get("focusable")):
            continue
        if label and len(label) > 2:
            continue
        score = 3.0 if node.get("editable") else 0.0
        score += 1.5 if not label else 0.0
        score += max(0.0, 1.0 - abs(cx / max(1, obs.image_width) - 0.18))
        score += max(0.0, 1.0 - abs(cy / max(1, obs.image_height) - 0.32))
        if score > best_score:
            best_score = score
            best = node
    return best


def empty_rounded_input_coords(obs: Observation) -> Optional[list[int]]:
    """Find the left-aligned rounded empty box under the question (age layout)."""
    if not obs.screenshot or not Path(obs.screenshot).exists():
        return None
    try:
        with Image.open(obs.screenshot) as source:
            image = source.convert("RGB")
            width, height = image.size
            pixels = image.load()
            tops: list[tuple[int, int, int]] = []
            min_run = int(width * 0.14)
            for y in range(int(height * 0.18), int(height * 0.62)):
                run = 0
                start = 0
                best_len = 0
                best = (0, 0)
                for x in range(int(width * 0.03), int(width * 0.55)):
                    red, green, blue = pixels[x, y]
                    grayish = abs(red - green) <= 12 and abs(green - blue) <= 12
                    if grayish and 170 <= red <= 225:
                        if run == 0:
                            start = x
                        run += 1
                        if run > best_len:
                            best_len = run
                            best = (start, x)
                    else:
                        run = 0
                if best_len >= min_run:
                    tops.append((y, best[0], best[1]))
            if not tops:
                return None
            clusters: list[list[tuple[int, int, int]]] = []
            for row in tops:
                if not clusters or row[0] - clusters[-1][-1][0] > 6:
                    clusters.append([row])
                else:
                    clusters[-1].append(row)

            def cluster_score(cluster: list[tuple[int, int, int]]) -> float:
                y_mid = cluster[len(cluster) // 2][0]
                left = min(item[1] for item in cluster)
                right = max(item[2] for item in cluster)
                rel_y = y_mid / max(1, height)
                rel_x = left / max(1, width)
                rel_w = (right - left) / max(1, width)
                score = 0.0
                if 0.25 <= rel_y <= 0.34:
                    score += 5.0
                if rel_x <= 0.12:
                    score += 4.0
                if 0.18 <= rel_w <= 0.38:
                    score += 3.0
                if rel_y >= 0.68:
                    score -= 6.0  # Back/Continue bar, not the field
                if 0.36 <= rel_y <= 0.58:
                    score += 2.0  # Child-age box sits lower when the red banner is up
                return score

            cluster = max(clusters, key=cluster_score)
            y_top = cluster[len(cluster) // 2][0]
            x1 = min(item[1] for item in cluster)
            x2 = max(item[2] for item in cluster)
            box_h = int(height * 0.055)
            cx = (x1 + x2) // 2
            cy = y_top + max(36, box_h // 2)
            coords = [
                int(max(0, min(1000, cx * 1000 / max(1, width)))),
                int(max(0, min(1000, cy * 1000 / max(1, height)))),
            ]
            logger.info(
                "[TEXT FIELD] Rounded empty box top=%s span=%s..%s tap=%s",
                y_top, x1, x2, coords,
            )
            return coords
    except Exception as exc:
        logger.debug("Rounded input detection unavailable: %s", exc)
        return None


def below_instruction_coords(obs: Observation) -> Optional[list[int]]:
    """Tap inside the box under 'Enter a number', not on the question title."""
    if not obs.screenshot or not Path(obs.screenshot).exists():
        return None
    preferred = None
    fallback_q = None
    try:
        for psm in (11, 6, 3):
            for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                label = node_text(node).lower()
                bounds = node.get("bounds") or []
                if len(bounds) != 4:
                    continue
                if any(term in label for term in ("enter a number", "enter your", "type your")):
                    preferred = bounds
                    break
                if fallback_q is None and "age" in label and "?" in label:
                    fallback_q = bounds
            if preferred:
                break
        bounds = preferred or fallback_q
        if not bounds:
            return None
        x1, y1, x2, y2 = [int(v) for v in bounds]
        tap_x = int(obs.image_width * 0.18)
        # 8% of screen below the instruction lands in the rounded box; 3% hit the title.
        offset = int(obs.image_height * (0.055 if preferred else 0.09))
        tap_y = y2 + offset
        return [
            int(max(0, min(1000, tap_x * 1000 / max(1, obs.image_width)))),
            int(max(0, min(1000, tap_y * 1000 / max(1, obs.image_height)))),
        ]
    except Exception as exc:
        logger.debug("Instruction field grounding unavailable: %s", exc)
        return None


def text_entry_field_candidates(obs: Observation) -> list[list[int]]:
    """Ordered tap targets for an empty WebView text field."""
    candidates: list[list[int]] = []

    def add(coords: Optional[list[int]]) -> None:
        if not isinstance(coords, list) or len(coords) != 2:
            return
        key = (int(coords[0]), int(coords[1]))
        if any((int(item[0]), int(item[1])) == key for item in candidates):
            return
        # Question-title zone: y<0.24 is the heading, not the box.
        if coords[1] < 240:
            return
        candidates.append([int(coords[0]), int(coords[1])])

    keyboard = soft_keyboard_visible(obs)
    if keyboard:
        add([500, 340])
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if "any other" in blob or "please provide an answer" in blob:
        add([500, 620])

    node = clickable_empty_field_node(obs)
    if node:
        cx, cy = node_center(node)
        add([
            int(max(0, min(1000, cx * 1000 / max(1, obs.image_width)))),
            int(max(0, min(1000, cy * 1000 / max(1, obs.image_height)))),
        ])
    add(empty_rounded_input_coords(obs))
    add(below_instruction_coords(obs))
    visual = visual_text_field_coords(obs)
    kb_key = resolve_text_kb_key(obs.ocr_text)
    if kb_key == "age":
        if visual != [500, 750]:
            add(visual)
        add([180, 310])
        add([200, 340])
    else:
        add(visual)
    if keyboard:
        filtered = [item for item in candidates if int(item[1]) < 560]
        if filtered:
            return filtered
        return [[500, 340]]
    return candidates or [[500, 380]]


def text_entry_field_coords(obs: Observation, stagnation_count: int = 0) -> list[int]:
    """Tap the empty input box using the D22-style locate-then-type work habit."""
    candidates = text_entry_field_candidates(obs)
    index = min(max(0, int(stagnation_count)), len(candidates) - 1)
    chosen = candidates[index]
    logger.info(
        "[TEXT FIELD] Using candidate %s/%s coords=%s all=%s",
        index + 1, len(candidates), chosen, candidates,
    )
    return chosen




def looks_like_captcha_code(text: str) -> bool:
    token = re.sub(r"[^A-Za-z0-9]", "", str(text or ""))
    if not (4 <= len(token) <= 10):
        return False
    if token.lower() in {"please", "following", "survey", "privacy", "english", "policy", "next"}:
        return False
    letters = sum(ch.isalpha() for ch in token)
    if letters < 3:
        return False
    mixed = any(ch.islower() for ch in token) and any(ch.isupper() for ch in token)
    return mixed or (not token.isalpha())


def captcha_code_from_ocr_text(ocr_text: str) -> str:
    for token in re.findall(r"[A-Za-z][A-Za-z0-9]{3,9}", str(ocr_text or "")):
        if looks_like_captcha_code(token):
            return token
    return ""


def captcha_field_complete(obs: Observation) -> bool:
    stored = _CAPTCHA_TYPED.get("captcha_code", "")
    return bool(looks_like_captcha_code(stored))


def captcha_field_coords(obs: Observation) -> list[int]:
    if soft_keyboard_visible(obs):
        return [180, 400]
    return [180, 640]


def captcha_code_from_image(obs: Observation) -> str:
    if not obs.screenshot or not Path(obs.screenshot).exists():
        return ""
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            width, height = rgb.size
            keyboard = soft_keyboard_visible(obs)
            y1 = int(height * (0.18 if keyboard else 0.38))
            y2 = int(height * (0.40 if keyboard else 0.62))
            x1, x2 = int(width * 0.12), int(width * 0.72)
            crop = rgb.crop((x1, y1, x2, y2)).resize(
                (max(8, (x2 - x1) * 3), max(8, (y2 - y1) * 3))
            )
            gray = crop.convert("L")
        whitelist = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        for psm in (7, 8, 13):
            raw = pytesseract.image_to_string(
                gray, config=f"--oem 3 --psm {psm} -c tessedit_char_whitelist={whitelist}"
            )
            token = captcha_code_from_ocr_text(raw) or re.sub(r"[^A-Za-z0-9]", "", raw or "")
            if looks_like_captcha_code(token):
                logger.info("[CAPTCHA] Tesseract code=%r psm=%s", token, psm)
                return token
    except Exception as exc:
        logger.warning("[CAPTCHA] Image OCR failed: %s", exc)
    return ""


def captcha_code_from_vlm(obs: Observation) -> str:
    if not obs.screenshot or not Path(obs.screenshot).exists():
        return ""
    try:
        raw = call_llm(
            "Read the distorted captcha/code in the screenshot. Reply JSON only: "
            "{\"action\":\"type_text\",\"input_payload\":\"TheCode\"} "
            "with the exact letters/digits, preserving case. Do not click Next.",
            Path(obs.screenshot),
            "JSON {\"input_payload\":\"code\"} only.",
        )
        data = parse_json_response(raw)
        token = re.sub(r"[^A-Za-z0-9]", "", str(data.get("input_payload") or data.get("code") or ""))
        if looks_like_captcha_code(token):
            logger.info("[CAPTCHA] VLM code=%r", token)
            return token
    except Exception as exc:
        logger.warning("[CAPTCHA] VLM read failed: %s", exc)
    return ""


def drag_drop_target_value(ocr_text: str) -> str:
    blob = re.sub(r"\s+", " ", str(ocr_text or ""))
    match = re.search(r"(?i)(?:drop|drag)\s+(?:and\s+drop\s+)?(?:the\s+)?(?:number\s+)?([A-Za-z0-9]{1,4})", blob)
    if match:
        return match.group(1)
    match = re.search(r"(?i)number\s+(\d{1,4})", blob)
    return match.group(1) if match else ""


def drag_drop_source_coords(obs: Observation, value: str) -> list[int]:
    if value and obs.screenshot and Path(obs.screenshot).exists():
        try:
            center = ocr_text_center(Path(obs.screenshot), value)
            if center and center[1] >= obs.image_height * 0.28:
                return [
                    int(max(80, min(920, center[0] * 1000 / max(1, obs.image_width)))),
                    int(max(280, min(700, center[1] * 1000 / max(1, obs.image_height)))),
                ]
        except Exception as exc:
            logger.debug("Drag source OCR unavailable: %s", exc)
    return [500, 455]


def drag_drop_dest_coords(obs: Observation, source: list[int]) -> list[int]:
    dest_y = min(760, max(int(source[1]) + 170, 600))
    return [500, dest_y]


def drag_drop_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Drag the requested tile into the dashed square, then Next."""
    if not drag_drop_question_visible(obs.ocr_text):
        _DRAG_DONE.pop("done", None)
        return None
    if _DRAG_DONE.get("done"):
        logger.info("[DRAG] Tile already dropped; grounding Next.")
        return captcha_next_decision(obs)
    value = drag_drop_target_value(obs.ocr_text) or "75"
    start = drag_drop_source_coords(obs, value)
    end = drag_drop_dest_coords(obs, start)
    logger.info("[DRAG] %s from %s to drop box %s", value, start, end)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Drag and drop {value} into the square box.",
        "action": "drag",
        "target_element_id": None,
        "target_text": value,
        "target_coords": start,
        "gesture_start": start,
        "gesture_end": end,
        "coordinate_authoritative": True,
        "input_payload": value,
        "kb_key": None,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.93,
        "postcondition": "screen changed",
        "visual_reasoning": "The instruction is a drag-and-drop of one numbered tile into the dashed box.",
        "answer_provenance": "inferred",
        "source_basis": "Visible drag-and-drop prompt",
        "inference_confidence": 0.9,
    }


def adult_age_question_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if any(token in blob for token in (
        "state their ages", "their ages", "child's age", "age of your child",
    )):
        return False
    return bool(re.search(r"what is your age|how old are you", blob))


def adult_age_payload(obs: Observation) -> str:
    raw = kb_or_persona_value(obs, "age")
    if raw in (None, ""):
        raw = 44
    text = str(raw).strip()
    if text.lstrip("-").replace(".", "", 1).isdigit():
        return str(int(float(text)))
    return text.split()[0]


def adult_age_in_field(obs: Observation, wanted: str) -> bool:
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    if "please specify a whole number" in blob or "please enter a whole number" in blob:
        return False
    if survey_validation_error(obs):
        return False
    return bool(wanted and re.search(rf"(?<!\d){re.escape(str(wanted))}(?!\d)", blob))


def adult_age_field_coords(obs: Observation) -> list[int]:
    found = empty_rounded_input_coords(obs)
    if found and 280 <= int(found[1]) <= 650:
        return found
    return found or [500, 440]


def adult_age_continue_coords(obs: Observation) -> list[int]:
    hit = gender_continue_milli(obs)
    if hit:
        return hit
    for bar in orange_cta_milli(obs, 0.34, 0.62):
        if 360 <= int(bar[1]) <= 580:
            return [int(bar[0]), int(bar[1])]
    return [500, 455]


def adult_age_screen_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Object model: empty age box → type KB age; then tap the orange Continue bar."""
    if not adult_age_question_visible(obs.ocr_text):
        return None
    wanted = adult_age_payload(obs)
    if not adult_age_in_field(obs, wanted):
        coords = adult_age_field_coords(obs)
        logger.info("[AGE] Type knowledge_base.json:age=%s at %s", wanted, coords)
        return {
            "screen_state": "survey_question", "action": "type_text",
            "target_text": "age input field", "target_coords": coords,
            "coordinate_authoritative": True, "input_payload": wanted, "kb_key": "age",
            "confidence_score": 0.99, "postcondition": f"field contains {wanted}",
            "answer_reason": f"knowledge_base.json:age={wanted}. Type it, then Continue.",
        }
    coords = adult_age_continue_coords(obs)
    logger.info("[AGE] %s is in the box; Continue at %s", wanted, coords)
    return {
        "screen_state": "survey_question", "action": "click", "target_text": "Continue",
        "target_coords": coords, "coordinate_authoritative": True, "kb_key": "age",
        "confidence_score": 0.97, "postcondition": "screen changed",
        "answer_reason": f"Age {wanted} typed; tap the orange Continue bar.",
    }
