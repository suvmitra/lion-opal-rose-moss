# 04_rank_likert.py — shared engine namespace (do not import directly)

def ranking_question_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return any(phrase in text for phrase in (
        "click or drag each item",
        "drag each item",
        "into a rank position",
        "place them in the order",
        "tier hierarchy",
        "please rate at least",
        "rate at least",
        "rank the following",
        "order you believe",
        "from the entry-level",
        "highest-status",
    ))


_RANK_CHROME = (
    "%", "progress", "complete", "survey", "problem", "question", "please",
    "click", "drag", "hierarchy", "membership", "accessibility", "help",
    "facebook", "select one", "continue", "back", "there were", "data you",
    "find the", "follow the", "instruction", "below are", "based only",
    "place them", "order you", "entry-level", "highest", "rate at",
    "statement", "qualified", "cookie",
)


_RANK_TIER_WORDS = (
    "emerald", "gold", "silver", "bronze", "platinum", "diamond", "titanium",
    "signature", "premier", "select", "elite",
)


def looks_like_rank_card(label: str, node: Optional[dict[str, Any]] = None, obs: Optional[Observation] = None) -> bool:
    text = _normalize_space(label)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 +/&'-]{0,39}", text):
        return False
    if len(text) < 4 or not (1 <= len(text.split()) <= 5):
        return False
    lowered = text.lower()
    if not any(token in lowered for token in _RANK_TIER_WORDS):
        return False
    if any(token in lowered for token in ("mid-tier", "base tier", "top tier", "reward")):
        return False
    if any(token in lowered for token in _RANK_CHROME):
        return False
    if is_progression_cta(text) or is_forbidden_progression_target(text):
        return False
    if node and obs:
        bounds = node.get("bounds") or []
        if len(bounds) == 4:
            height = max(1, int(obs.image_height or 0))
            width = max(1, int(obs.image_width or 0))
            y1, y2 = int(bounds[1]), int(bounds[3])
            card_w = int(bounds[2]) - int(bounds[0])
            if y1 < int(height * 0.26) or y2 > int(height * 0.84):
                return False
            if card_w < int(width * 0.32):
                return False
    return True


def rank_card_is_placed(obs: Observation, node: Optional[dict[str, Any]]) -> bool:
    """Teal fill on a rank bar means that item already has a rank number."""
    if not node or not obs.screenshot:
        return False
    path = Path(obs.screenshot)
    if not path.exists():
        return False
    bounds = node.get("bounds") or []
    if len(bounds) != 4:
        return False
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            x1, y1, x2, y2 = [int(v) for v in bounds]
            x1 = max(0, min(rgb.width - 1, x1 + 8))
            x2 = max(0, min(rgb.width, x2 - 8))
            y1 = max(0, min(rgb.height - 1, y1 + 8))
            y2 = max(0, min(rgb.height, y2 - 8))
            if x2 <= x1 or y2 <= y1:
                return False
            hits = 0
            step_x = max(1, (x2 - x1) // 12)
            step_y = max(1, (y2 - y1) // 6)
            for y in range(y1, y2, step_y):
                for x in range(x1, x2, step_x):
                    r, g, b = rgb.getpixel((x, y))[:3]
                    if r < 100 and g > 145 and b > 140 and (g - r) > 45:
                        hits += 1
            return hits >= 8
    except Exception:
        return False


def ranking_item_labels(obs: Observation) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    def add(label: str) -> None:
        text = _normalize_space(label)
        key = text.lower()
        if not text or key in seen:
            return
        if len(text) < 4 or not any(token in key for token in _RANK_TIER_WORDS):
            return
        if any(token in key for token in ("reward", "loyalty", "survey", "continue", "accessibility", "mid-tier")):
            return
        seen.add(key)
        items.append(text)

    for node in obs.ui_nodes:
        label = node_text(node)
        if looks_like_rank_card(label, node, obs):
            add(label)
    for raw in str(obs.ocr_text or "").splitlines():
        line = _normalize_space(raw)
        for match in re.finditer(
            r"\b(?:Gold|Silver|Bronze|Platinum|Diamond|Titanium|Emerald(?:\s+(?:Premier|Select|Signature|Plus|Elite))?)\b",
            line,
            flags=re.I,
        ):
            add(match.group(0))
        if looks_like_rank_card(line):
            add(line)
    return items


def intended_rank_order(items: list[str]) -> list[str]:
    """Base/entry first, highest-status last, from the visible names."""
    def score(name: str) -> tuple[int, int]:
        lowered = name.lower()
        rank = 0
        if any(token in lowered for token in ("premier", "platinum", "diamond", "elite", "top")):
            rank += 40
        if "emerald" in lowered:
            rank += 32
        if "signature" in lowered:
            rank += 30
        if any(token in lowered for token in ("select", "plus", "gold")):
            rank += 20
        if "bronze" in lowered:
            rank += 5
        if "silver" in lowered:
            rank += 10
        return (rank, len(lowered))
    return sorted(items, key=score)


def ranking_item_node(obs: Observation, target: str) -> Optional[dict[str, Any]]:
    wanted = normalize_choice(target)
    exact: list[dict[str, Any]] = []
    for node in obs.ui_nodes:
        label = node_text(node)
        if normalize_choice(label) == wanted:
            exact.append(node)
    if exact:
        on_screen = [node for node in exact if cta_node_on_screen(node, obs) or True]
        return max(on_screen, key=lambda node: node_area(node) if "node_area" in globals() else (
            (node.get("bounds") or [0, 0, 0, 0])[2] - (node.get("bounds") or [0, 0, 0, 0])[0]
        ))
    return option_node_for_text(obs, target)


def ranking_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tap each unranked gray card Base→Top, then Continue. Never tap chrome."""
    if not ranking_question_visible(obs.ocr_text):
        return None
    items = ranking_item_labels(obs)
    if len(items) < 2:
        logger.info("[RANK] Ranking screen detected but items were not parsed from OCR/UI.")
        return None
    order = intended_rank_order(items)
    key = question_fingerprint(obs)
    done = _RANK_PROGRESS.setdefault(key, [])
    for label in order:
        node = ranking_item_node(obs, label)
        if rank_card_is_placed(obs, node) and label not in done:
            done.append(label)
            logger.info("[RANK] Visual teal already placed %r", label)
    remaining = [item for item in order if item.lower() not in {str(x).lower() for x in done}]
    if remaining:
        target = remaining[0]
        node = ranking_item_node(obs, target)
        coords = None
        if node and node.get("bounds") and len(node.get("bounds") or []) == 4:
            x1, y1, x2, y2 = [int(v) for v in node["bounds"]]
            coords = [
                int(((x1 + x2) / 2) * 1000 / max(1, obs.image_width)),
                int(((y1 + y2) / 2) * 1000 / max(1, obs.image_height)),
            ]
        logger.info("[RANK] Placing %r (%s remaining after this tap)", target, remaining[1:])
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Rank {target} in Base-to-Top order {order}.",
            "action": "click",
            "target_element_id": node.get("id") if node else None,
            "target_text": target,
            "target_coords": coords,
            "coordinate_authoritative": bool(coords),
            "input_payload": target,
            "kb_key": "membership_tier_rank",
            "kb_write": False,
            "missing_fact_key": None,
            "confidence_score": 0.92,
            "postcondition": f"ranked item is {target}",
            "visual_reasoning": "Ranking widget requires each unranked gray card to be tapped.",
            "answer_provenance": "inferred",
            "source_basis": "Visible tier names, Base→Top (Emerald < Select < Premier)",
            "inference_confidence": 0.86,
            "selection_complete": False,
            "rank_item": target,
        }
    if not ranking_complete(obs):
        logger.warning("[RANK] Only %s placed, need 3+; not Continue. items=%s", done, order)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": "Please rate at least 3 items. A gray bar is still unranked.",
            "action": "wait",
            "confidence_score": 0.7,
            "postcondition": "screen stable for re-observation",
        }
    logger.info("[RANK] All %s items placed; grounding Continue.", order)
    return survey_next_decision(obs)


def likert_slider_question_visible(ocr_text: str, nodes: Optional[list] = None) -> bool:
    if ranking_question_visible(ocr_text):
        return False
    blob = str(ocr_text or "")
    if nodes:
        blob += " " + " ".join(node_text(node) for node in nodes if node_text(node))
    text = re.sub(r"\s+", " ", blob.lower().replace("’", "'").replace("‘", "'"))
    if any(phrase in text for phrase in (
        "slide the handle",
        "drag the slider",
        "like it very",
        "don't like it",
        "dont like it",
        "please slide",
        "rate how much you like",
        "dislike each",
    )):
        return True
    return "emerald" in text and "like" in text and re.search(r"\b[1-5]\b", text) is not None


_LIKERT_VALUE_CYCLE = (3, 4, 5, 4, 3)
_LIKERT_HEADERS = ("Emerald Signature", "Emerald Premier", "Emerald Select", "Emerald")


def likert_node_on_screen(node: Optional[dict[str, Any]], obs: Observation) -> bool:
    if not node:
        return False
    bounds = node.get("bounds") or []
    if len(bounds) != 4:
        return False
    x1, y1, x2, y2 = [int(v) for v in bounds]
    height = max(1, int(obs.image_height or 0))
    width = max(1, int(obs.image_width or 0))
    if (y2 - y1) < 16 or (x2 - x1) < 8:
        return False
    mid_y = (y1 + y2) / 2
    if mid_y < height * 0.12 or mid_y > height * 0.90:
        return False
    if x2 <= 0 or x1 >= width:
        return False
    return True


def likert_groups(obs: Observation) -> list[dict[str, Any]]:
    headers: dict[str, dict[str, Any]] = {}
    for node in obs.ui_nodes:
        label = node_text(node).strip()
        if label not in _LIKERT_HEADERS or not likert_node_on_screen(node, obs):
            continue
        prev = headers.get(label)
        if prev is None or node_center(node)[1] < prev["y"]:
            headers[label] = {"name": label, "node": node, "y": node_center(node)[1]}
    ratings: list[dict[str, Any]] = []
    for node in obs.ui_nodes:
        raw = node_text(node).strip()
        match = re.match(r"^([1-5])(?:\s*[-–].*)?$", raw)
        if not match or not likert_node_on_screen(node, obs):
            continue
        ratings.append({
            "value": int(match.group(1)),
            "node": node,
            "text": raw,
            "y": node_center(node)[1],
        })
    ordered = sorted(headers.values(), key=lambda item: item["y"])
    groups: list[dict[str, Any]] = []
    for index, header in enumerate(ordered):
        y_min = header["y"] - 40
        y_max = ordered[index + 1]["y"] - 20 if index + 1 < len(ordered) else int(obs.image_height * 0.88)
        group_ratings = [item for item in ratings if y_min < item["y"] < y_max]
        groups.append({**header, "ratings": group_ratings})
    return groups


def likert_group_visually_rated(obs: Observation, group: dict[str, Any]) -> bool:
    """Teal knob on 3/4/5 means this scale already has a value."""
    if not obs.screenshot or not Path(str(obs.screenshot)).exists():
        return False
    try:
        with Image.open(obs.screenshot) as image:
            rgb = image.convert("RGB")
            pixels = rgb.load()
            hits = 0
            for item in group.get("ratings") or []:
                if item["value"] not in {3, 4, 5}:
                    continue
                bounds = (item["node"] or {}).get("bounds") or []
                if len(bounds) != 4:
                    continue
                x1, y1, x2, y2 = [int(v) for v in bounds]
                cx = max(8, x1 - 90)
                cy = int((y1 + y2) / 2)
                for dx in range(-18, 19, 3):
                    for dy in range(-18, 19, 3):
                        xx, yy = cx + dx, cy + dy
                        if 0 <= xx < rgb.width and 0 <= yy < rgb.height:
                            red, green, blue = pixels[xx, yy][:3]
                            if red < 90 and green > 145 and blue > 140 and (green - red) > 50:
                                hits += 1
            return hits >= 10
    except Exception:
        return False


def likert_tap_coords(obs: Observation, node: Optional[dict[str, Any]]) -> Optional[list[int]]:
    if not node or not likert_node_on_screen(node, obs):
        return None
    x1, y1, x2, y2 = [int(v) for v in (node.get("bounds") or [0, 0, 0, 0])]
    cy = int((y1 + y2) / 2)
    cx = x1 - 110
    if cx < int(obs.image_width * 0.06):
        cx = int((x1 + x2) / 2)
    nx = int(cx * 1000 / max(1, obs.image_width))
    ny = int(cy * 1000 / max(1, obs.image_height))
    if ny < 200 or ny > 860 or nx < 40 or nx > 900:
        return None
    return [nx, ny]


def likert_scroll_decision(obs: Observation, missing: list[str], used: int) -> dict[str, Any]:
    sequence = ["scroll_down", "scroll_down", "scroll_down", "scroll_up", "scroll_left", "scroll_right", "scroll_down", "scroll_up"]
    action = sequence[used % len(sequence)]
    logger.info("[LIKERT] Scroll %s to find %s (%s/8).", action, missing, used + 1)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Do not Continue. Scroll until unrated scales {missing} are on screen.",
        "action": action,
        "confidence_score": 0.92,
        "postcondition": "unrated scale visible",
        "visual_reasoning": "Unrated scales sit below/above the fold; Continue is blocked.",
    }

def likert_names_on_page(obs: Observation) -> list[str]:
    blob = " ".join(
        [str(obs.ocr_text or "")] + [node_text(node) for node in obs.ui_nodes]
    ).lower()
    names: list[str] = []
    if "emerald signature" in blob:
        names.append("Emerald Signature")
    if "emerald premier" in blob:
        names.append("Emerald Premier")
    if "emerald select" in blob:
        names.append("Emerald Select")
    if re.search(r"(?i)\bemerald\b(?!\s+(select|premier|signature|rewards))", blob):
        names.append("Emerald")
    return names


def likert_missing_names(obs: Observation) -> list[str]:
    done = {str(item) for item in _LIKERT_PROGRESS.get(question_fingerprint(obs), [])}
    required = likert_names_on_page(obs)
    if not required:
        required = [group["name"] for group in likert_groups(obs)]
    return [name for name in required if name not in done]


def likert_complete(obs: Observation) -> bool:
    if not likert_slider_question_visible(obs.ocr_text):
        return False
    return not likert_missing_names(obs)


def likert_slider_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Tap 3/4/5 on each like-dislike scale, then Continue. No VLM required."""
    if not likert_slider_question_visible(obs.ocr_text):
        return None
    groups = likert_groups(obs)
    key = question_fingerprint(obs)
    done = _LIKERT_PROGRESS.setdefault(key, [])
    for group in groups:
        if group["name"] not in done and likert_group_visually_rated(obs, group):
            done.append(group["name"])
            logger.info("[LIKERT] Visual teal already on %r; skipping.", group["name"])
    missing = likert_missing_names(obs)
    remaining = [group for group in groups if group["name"] in missing and group.get("ratings")]
    if remaining:
        group = remaining[0]
        value = _LIKERT_VALUE_CYCLE[len(done) % len(_LIKERT_VALUE_CYCLE)]
        rating = next((item for item in group["ratings"] if item["value"] == value), None)
        if rating is None:
            rating = min(group["ratings"], key=lambda item: abs(item["value"] - value))
        node = rating["node"]
        coords = likert_tap_coords(obs, node)
        if not coords:
            used = _LIKERT_SCROLLS.get(key, 0)
            if used < 8:
                _LIKERT_SCROLLS[key] = used + 1
                return likert_scroll_decision(obs, missing, used)
        logger.info("[LIKERT] %s -> %s remaining_after=%s coords=%s", group["name"], rating["text"], missing[1:], coords)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Rate {group['name']} at {value} on the like/dislike scale.",
            "action": "click",
            "target_element_id": node.get("id") if node else None,
            "target_text": rating["text"],
            "target_coords": coords,
            "coordinate_authoritative": bool(coords),
            "input_payload": str(value),
            "kb_key": None,
            "kb_write": False,
            "missing_fact_key": None,
            "confidence_score": 0.9,
            "postcondition": f"likert {group['name']} rated {value}",
            "visual_reasoning": "Each named scale must be tapped before Continue.",
            "answer_provenance": "inferred",
            "source_basis": "Visible 1-5 like/dislike slider; cycle 3,4,5",
            "inference_confidence": 0.8,
            "likert_item": group["name"],
        }
    if missing:
        used = _LIKERT_SCROLLS.get(key, 0)
        if used < 8:
            _LIKERT_SCROLLS[key] = used + 1
            return likert_scroll_decision(obs, missing, used)
        logger.warning("[LIKERT] Missing %s after directional scrolls; tapping first visible scale.", missing)
        visible = [group for group in groups if group.get("ratings")]
        if visible:
            group = visible[0]
            rating = next((item for item in group["ratings"] if item["value"] == 3), group["ratings"][0])
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": f"Rate visible scale {group['name']} at 3. Do not hunt names that are not on this page.",
                "action": "click",
                "target_element_id": rating["node"].get("id"),
                "target_text": rating["text"],
                "target_coords": likert_tap_coords(obs, rating["node"]),
                "coordinate_authoritative": True,
                "input_payload": "3",
                "confidence_score": 0.85,
                "postcondition": f"likert {group['name']} rated 3",
                "likert_item": group["name"],
            }
        return survey_next_decision(obs)
    logger.info("[LIKERT] All required scales rated; grounding Continue.")
    return survey_next_decision(obs)


def classify_screen_phase(ocr_text: str, nodes: list[dict[str, Any]]) -> str:
    """Classify before prompting so answer memory cannot contaminate navigation."""
    visible = re.sub(r"\s+", " ", ocr_text.lower())
    structured = re.sub(
        r"\s+", " ", " ".join(node_text(n) for n in nodes if node_text(n)).lower()
    )
    combined = f"{visible} {structured}"

    if any(term in visible for term in ("thank you for completing", "survey completed", "reward earned")):
        return "completion"
    if any(term in combined for term in TERMINAL_SURVEY_PHRASES):
        return "terminal_modal"
    if permission_dialog_visible(ocr_text, nodes):
        return "permission_dialog"
    if document_picker_visible(ocr_text, nodes):
        return "document_picker"
    if cookie_consent_visible(ocr_text, nodes):
        return "consent_overlay"
    # Current visible landing evidence outranks stale catalog nodes exposed by
    # the WebView underneath the qualified overlay.
    if qualified_landing_visible(ocr_text):
        return "survey_landing"
    if start_gate_visible(ocr_text):
        return "survey_landing"
    # Visible OCR wins over possibly stale/covered nodes from the app behind a
    # WebView or modal overlay.
    if "qualification" in visible or "few questions before the survey" in visible:
        return "survey_question"
    if any(term in visible for term in ("please wait", "loading...", "survey is loading")):
        return "loading"
    is_dashboard, _ = dashboard_evidence(ocr_text, nodes)
    if is_dashboard:
        return "dashboard"
    if carousel_row_question_visible(ocr_text):
        return "survey_question"
    if child_ages_question_visible(ocr_text):
        return "survey_question"
    if text_entry_question_visible(ocr_text, nodes):
        return "survey_question"
    if likert_slider_question_visible(ocr_text, nodes):
        return "survey_question"
    if ranking_question_visible(ocr_text):
        return "survey_question"
    if matrix_semantic_hint(ocr_text):
        return "survey_question"
    if looks_like_single_choice(ocr_text) or select_all_apply_visible(ocr_text):
        return "survey_question"
    if "please select an answer" in visible or "buy another brand" in visible:
        return "survey_question"
    if "?" in visible or (
        re.search(r"\bquestions?\s+\d+\s*/\s*\d+\b", visible)
        and any(term in visible for term in ("yes,", "no,", "select", "choose"))
    ):
        return "survey_question"
    if landing_cta_visible(ocr_text, nodes):
        return "survey_landing"
    if "?" in combined or any(n.get("checkable") or n.get("editable") for n in nodes):
        return "survey_question"
    return "navigation"


_COMFORT_OPTIONS = (
    "Very comfortable",
    "Somewhat comfortable",
    "Neutral",
    "Somewhat uncomfortable",
    "Very uncomfortable",
)
_COMFORT_SESSION: dict[str, Any] = {
    "topic": "", "picked": False, "pick_issued": False,
}


def comfort_scale_visible(ocr_text: str) -> bool:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return "very comfortable" in text and ("somewhat comfortable" in text or "neutral" in text)


def comfort_scale_topic(ocr_text: str) -> str:
    text = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    for name in (
        "payment", "purchase", "microphone", "location", "camera", "contacts",
        "photos", "messages", "health", "fitness", "calendar", "browsing",
    ):
        if name in text:
            return name
    return "item"


def comfort_scale_pick(ocr_text: str) -> str:
    topic = comfort_scale_topic(ocr_text)
    if topic in {"payment", "purchase"}:
        return "Somewhat uncomfortable"
    return "Neutral"


def comfort_option_milli(obs: Observation, pick: str) -> list[int]:
    mapped = select_n_map_checkbox_milli(obs, pick) if "select_n_map_checkbox_milli" in globals() else None
    if mapped:
        return [500, int(mapped[1])]
    index = list(_COMFORT_OPTIONS).index(pick) if pick in _COMFORT_OPTIONS else 2
    return [500, 410 + index * 78]


def comfort_likert_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """One Likert card per topic, then the footer arrow. Never tap the question title."""
    header = (
        comfort_question_header_visible(obs.ocr_text)
        if "comfort_question_header_visible" in globals() else False
    )
    options_on_screen = comfort_scale_visible(obs.ocr_text)
    if not options_on_screen and not header:
        return None
    obs.screen_phase = "survey_question"
    seen_topic = comfort_scale_topic(obs.ocr_text)
    topic = (
        str(_COMFORT_SESSION.get("topic") or "item")
        if seen_topic == "item" and _COMFORT_SESSION.get("pick_issued")
        else seen_topic
    )
    pick = "Somewhat uncomfortable" if topic in {"payment", "purchase"} else "Neutral"
    if _COMFORT_SESSION.get("topic") != topic and seen_topic != "item":
        _COMFORT_SESSION.update({"topic": topic, "picked": False, "pick_issued": False})
    banner = "question is required" in re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    visual = []
    if "select_n_visually_checked" in globals() and not banner:
        visual = select_n_visually_checked(obs, list(_COMFORT_OPTIONS))
    selected = (not banner) and any(pick.lower()[:10] in str(v).lower() for v in visual)
    if banner:
        _COMFORT_SESSION["picked"] = False
        _COMFORT_SESSION["pick_issued"] = False
        selected = False
    if not options_on_screen and _COMFORT_SESSION.get("pick_issued"):
        settling = page_series_wait_decision(obs, maximum=2) if "page_series_wait_decision" in globals() else None
        if settling:
            return settling
        done = mapped_footer_progression_decision(
            obs, f"{pick} was verified for {topic}; no next series item appeared, so use the exact footer arrow."
        ) if "mapped_footer_progression_decision" in globals() else None
        if done:
            _COMFORT_SESSION["picked"] = True
            return done
    if not options_on_screen:
        return None
    if not selected:
        tap = comfort_option_milli(obs, pick)
        _COMFORT_SESSION["pick_issued"] = True
        logger.info("[COMFORT] SEE topic=%s pick=%s tap=%s visual=%s", topic, pick, tap, visual)
        return {
            "screen_state": "survey_question", "action": "select_option",
            "target_text": pick, "target_coords": tap, "coordinate_authoritative": True,
            "input_payload": pick, "kb_key": f"ai_access_{topic}_comfort", "kb_write": True,
            "confidence_score": 0.95, "postcondition": "selected option is " + pick,
            "answer_reason": f"Comfort Likert for {topic}: tap {pick}; answer any next page-series item before the footer.",
            "skip_object_grounding": True,
        }
    settling = page_series_wait_decision(obs) if "page_series_wait_decision" in globals() else None
    if settling:
        return settling
    arrow = footer_cta_milli(obs) if "footer_cta_milli" in globals() else [500, 890]
    _COMFORT_SESSION.update({"picked": True, "pick_issued": True})
    logger.info("[COMFORT] %s is gray; ARROW %s", pick, arrow)
    return {
        "screen_state": "survey_question", "action": "click", "target_text": "Continue",
        "target_coords": arrow, "coordinate_authoritative": True,
        "input_payload": pick, "kb_key": f"ai_access_{topic}_comfort", "kb_write": True,
        "confidence_score": 0.96, "postcondition": "screen changed",
        "answer_reason": f"{pick} is selected for {topic}; tap centred footer arrow {arrow}.",
        "skip_object_grounding": True, "object_kind": "button",
    }


def comfort_likert_regression_self_check() -> bool:
    ocr = (
        "This question is required\n"
        "How comfortable are you/ would you be with an AI assistant having access "
        "to each of the following functions and types of personal information?\n"
        "Location\nVery comfortable\nSomewhat comfortable\nNeutral\n"
        "Somewhat uncomfortable\nVery uncomfortable\n"
    )
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="comfort",
        ocr_text=ocr, ui_nodes=[], kb={}, persona={}, screen_phase="survey_question",
        survey_tiles=[],
    )
    _COMFORT_SESSION.update({"topic": "", "picked": False, "pick_issued": False})
    first = comfort_likert_decision(obs)
    pay = Observation(**{**obs.__dict__, "ocr_text": ocr.replace("Location", "Payment/purchase information")})
    _COMFORT_SESSION.update({"topic": "", "picked": False, "pick_issued": False})
    second = comfort_likert_decision(pay)
    gen = generalized_unseen_router(obs) if "generalized_unseen_router" in globals() else first
    passed = bool(
        comfort_scale_visible(ocr)
        and first and first.get("action") == "select_option"
        and first.get("target_text") == "Neutral"
        and first.get("action") != "click"
        and int((first.get("target_coords") or [0, 0])[0]) == 500
        and int((first.get("target_coords") or [0, 0])[1]) < 800
        and "how comfortable" not in str(first.get("target_text") or "").lower()
        and second and second.get("target_text") == "Somewhat uncomfortable"
        and (gen is None or str(gen.get("target_text") or "").lower() in {
            "neutral", "somewhat uncomfortable", "somewhat comfortable", "very comfortable",
        } or gen.get("skip_object_grounding"))
    )
    if passed:
        logger.info("[SELF-CHECK] Comfort Likert taps Neutral/card, never the question title.")
    else:
        logger.error("[SELF-CHECK] Comfort Likert failed first=%s second=%s gen=%s", first, second, gen)
    return passed
