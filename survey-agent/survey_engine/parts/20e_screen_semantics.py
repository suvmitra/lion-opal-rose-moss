# 20e_screen_semantics.py — exact option state and information-page semantics


def normalized_option_label(value: str) -> str:
    text = str(value or "").replace("’", "'").lower()
    text = re.sub(r"\b(?:radio|radio button|option|choice|button)\b\s*$", "", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def best_option_text_node(nodes: list[dict[str, Any]], target: str) -> Optional[dict[str, Any]]:
    """Prefer the exact label; never let Dublin match '...excluding Dublin'."""
    wanted = normalized_option_label(target)
    if not wanted:
        return None
    ranked: list[tuple[tuple[int, int, int, int], dict[str, Any]]] = []
    for node in nodes:
        label = normalized_option_label(node_text(node))
        if not label:
            continue
        exact = label == wanted
        partial = wanted in label or label in wanted
        if not exact and not partial:
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            continue
        area = max(1, (int(bounds[2]) - int(bounds[0])) * (int(bounds[3]) - int(bounds[1])))
        ranked.append(((0 if exact else 1, abs(len(label) - len(wanted)), area, int(bounds[1])), node))
    return min(ranked, key=lambda item: item[0])[1] if ranked else None


def exact_option_node(obs: Observation, target: str) -> Optional[dict[str, Any]]:
    candidates = list(obs.ui_nodes or [])
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        for psm in (11, 6, 3):
            candidates.extend(ocr_line_nodes(Path(str(obs.screenshot)), psm=psm))
    return best_option_text_node(candidates, target)


def selected_option_visual(obs: Observation, target: str) -> bool:
    """Require a filled radio/check mark on the same row as the exact target."""
    wanted = normalized_option_label(target)
    node = exact_option_node(obs, wanted)
    if not node:
        return False
    for item in obs.ui_nodes or []:
        if not (item.get("checked") or item.get("selected")):
            continue
        label = normalized_option_label(node_text(item))
        if label == wanted:
            return True
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return False
    image = cv2.imread(str(obs.screenshot))
    bounds = node.get("bounds") or []
    if image is None or len(bounds) != 4:
        return False
    height, width = image.shape[:2]
    target_y = (int(bounds[1]) + int(bounds[3])) // 2
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    blue = cv2.inRange(hsv, (88, 55, 35), (138, 255, 255))
    count, _, stats, centers = cv2.connectedComponentsWithStats(blue, 8)
    tolerance = max(32, int(height * 0.022))
    for index in range(1, count):
        x, y, bw, bh, area = [int(value) for value in stats[index]]
        cx, cy = centers[index]
        radio_shape = 0.55 <= bw / max(1, bh) <= 1.8 and 8 <= bw <= int(width * 0.12)
        if area >= 120 and radio_shape and cx <= width * 0.24 and abs(cy - target_y) <= tolerance:
            logger.info("[OPTION STATE] Exact target=%r selected at y=%s (label y=%s).", wanted, int(cy), target_y)
            return True
    return False


def information_notice_page(obs: Observation) -> bool:
    """A prose disclosure with Continue is not an unanswered form question."""
    if obs.screen_phase not in {"survey_question", "navigation", "survey_landing"}:
        return False
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower()).strip()
    if required_validation_visible(obs):
        return False
    if any(node.get("editable") or node.get("checkable") for node in obs.ui_nodes or []):
        return False
    has_cta = bool(re.search(r"\b(?:continue|next|proceed)\b", text)) or any(
        node.get("enabled", True) and node.get("clickable") and is_progression_cta(node_text(node))
        for node in obs.ui_nodes or []
    )
    if not has_cta:
        return False
    disclosure_hits = sum(token in text for token in (
        "share your eircode", "geodemographic", "details may be shared",
        "suppliers and partners", "retain your eircode", "24 months",
        "privacy", "will not be contacted", "will be deleted",
    ))
    asks_for_input = any(token in text for token in (
        "please enter", "type your", "select one", "select an answer",
        "please provide an answer", "fill in this field", "this question is required",
    ))
    return bool(disclosure_hits >= 2 and not asks_for_input)


def operator_progression_command(value: str) -> bool:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    return bool(
        re.search(r"\b(?:click|tap|press|choose|select)\b", text)
        and re.search(r"\b(?:continue|next|proceed|arrow|submit)\b", text)
    )
