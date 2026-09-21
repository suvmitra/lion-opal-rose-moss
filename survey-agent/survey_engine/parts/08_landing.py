# 08_landing.py — shared engine namespace (do not import directly)

def node_by_id(nodes: list[dict[str, Any]], node_id: Any) -> Optional[dict[str, Any]]:
    try:
        wanted = int(node_id)
    except (TypeError, ValueError):
        return None
    return next((n for n in nodes if n["id"] == wanted), None)


def normalized_to_native(coords: list[Any], image_size: tuple[int, int], device_size: tuple[int, int]) -> tuple[int, int]:
    x = max(0, min(1000, float(coords[0])))
    y = max(0, min(1000, float(coords[1])))
    iw, ih = image_size
    dw, dh = device_size
    # Screenshot pixels are the source coordinate frame. If screenshot and
    # device dimensions differ, map screenshot pixels to device coordinates.
    sx, sy = int(iw * x / 1000), int(ih * y / 1000)
    if dw > 0 and dh > 0:
        sx = int(sx * dw / iw)
        sy = int(sy * dh / ih)
    return sx, sy


def text_match_node(nodes: list[dict[str, Any]], target: str) -> Optional[dict[str, Any]]:
    def normalize_match_text(value: str) -> str:
        normalized = str(value or "").replace("’", "'").lower()
        # Tesseract frequently renders the standalone pronoun I as | or l.
        normalized = re.sub(r"(?<!\w)[|l](?!\w)", "i", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    target = normalize_match_text(target)
    if not target:
        return None

    exact = []
    partial = []
    for n in nodes:
        combined = normalize_match_text(
            " ".join(x for x in (n["text"], n["content_desc"]) if x)
        )
        if not combined:
            continue
        if combined == target:
            exact.append(n)
        elif target in combined or combined in target:
            partial.append(n)
    def node_area(node: dict[str, Any]) -> int:
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            return 10**12
        return max(1, int(bounds[2] - bounds[0]) * int(bounds[3] - bounds[1]))

    def rank(node: dict[str, Any]) -> tuple:
        bounds = node.get("bounds") or [0, 0, 0, 0]
        width = max(0, int(bounds[2]) - int(bounds[0])) if len(bounds) == 4 else 0
        y1 = int(bounds[1]) if len(bounds) == 4 else 0
        y2 = int(bounds[3]) if len(bounds) == 4 else 0
        header = 1 if y2 <= 220 or y1 < 100 else 0
        footer = 1 if y1 >= 2600 else 0
        tiny = 1 if node_area(node) < 4000 else 0
        huge = 1 if width >= 1200 and node_area(node) >= 1_000_000 else 0
        clickable = 0 if node.get("clickable") or node.get("checkable") else 1
        return (header, footer, tiny, huge, clickable, -node_area(node))

    ranked = sorted(exact or partial, key=rank)
    return ranked[0] if ranked else None


def ocr_text_center(path: Path, target: str) -> Optional[tuple[int, int]]:
    # Cached PSM 6 is enough for almost every label. PSM 11 only if the dense
    # pass misses, so we do not run Tesseract three times per word.
    for psm in (6, 11):
        match = text_match_node(ocr_line_nodes(path, psm=psm), target)
        if match:
            return node_center(match)
    return None


def choose_survey_tile_decision(
    obs: Observation,
    stagnation_count: int = 0,
    excluded_labels: Optional[set[str]] = None,
) -> Optional[dict[str, Any]]:
    if not obs.survey_tiles:
        return None

    def value_score(tile: dict[str, Any]) -> float:
        payout = float(tile.get("payout") or 0)
        duration = float(tile.get("duration_minutes") or 999)
        return payout / max(1.0, duration)

    if SURVEY_SELECTION_POLICY == "first_visible":
        ordered = list(obs.survey_tiles)
    else:
        ordered = sorted(obs.survey_tiles, key=value_score, reverse=True)
    excluded = {label.strip().lower() for label in (excluded_labels or set())}
    eligible = [
        tile for tile in ordered
        if str(tile.get("label") or "").strip().lower() not in excluded
    ]
    if eligible:
        ordered = eligible
    elif excluded:
        logger.warning(
            "[DASHBOARD ROUTER] All visible parsed cards are excluded; deferring to re-observation."
        )
        return None

    # If a tap did not change the screen, try a different parsed card rather
    # than calling the LLM with the same screenshot and repeating hallucinations.
    selected = ordered[min(stagnation_count, len(ordered) - 1)]
    x, y = selected["center"]
    coords = [
        int(max(0, min(1000, x * 1000 / max(1, obs.image_width)))),
        int(max(0, min(1000, y * 1000 / max(1, obs.image_height)))),
    ]
    logger.info(
        "[DASHBOARD ROUTER] Selected tile=%s policy=%s stagnation=%s excluded=%s coords=%s",
        selected, SURVEY_SELECTION_POLICY, stagnation_count, len(excluded), coords
    )
    return {
        "screen_state": "dashboard",
        "question_text": "",
        "answer_reason": "Open a parsed Featured Survey card before answering questions.",
        "action": "click",
        "target_element_id": None,
        "target_text": selected.get("label"),
        "target_coords": coords,
        "coordinate_authoritative": True,
        "input_payload": None,
        "kb_key": None,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.98,
        "postcondition": "screen changed",
        "visual_reasoning": "Structured duration/payout text was grouped into a visible survey card.",
        "answer_provenance": "verified",
        "source_basis": "Current screenshot and UI/OCR geometry",
        "inference_confidence": 0.98,
    }


def cta_node_on_screen(node: Optional[dict[str, Any]], obs: Observation) -> bool:
    """True when a CTA node's bounds sit in the screenshot content band."""
    if not node:
        return False
    bounds = node.get("bounds") or []
    if len(bounds) != 4:
        return False
    y1, y2 = int(bounds[1]), int(bounds[3])
    height = max(1, int(obs.image_height or 0))
    if y1 < 0 or y1 >= height or y2 <= int(height * 0.14):
        return False
    if y1 >= int(height * 0.88):
        return False
    return True


def info_page_needs_scroll(obs: Observation) -> bool:
    """True for qualified/instruction pages whose Continue control is below the fold."""
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower().replace("’", "'"))
    if visible_progression_label(obs.ocr_text):
        return False
    if visible_exact_label(obs.ocr_text, list(LANDING_CTA_LABELS) + ["Continue", "Next", "Continue »"]):
        return False
    if looks_like_single_choice(obs.ocr_text) or matrix_semantic_hint(obs.ocr_text):
        return False
    qualified = any(phrase in text for phrase in (
        "qualified for this survey",
        "we would like to get your feedback",
        "we would like your feedback",
        "potential new loyalty program",
    ))
    short_cues = any(phrase in text for phrase in (
        "click below to get started",
        "get started and earn",
        "survey will take around",
        "survey success tip",
    ))
    long_info = len(text) >= 350 and "?" not in text and "select one" not in text
    return bool((qualified and not short_cues) or long_info)


def scroll_until_cta_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Scroll a long info/landing page until Continue/Next/Participate is visible."""
    if not info_page_needs_scroll(obs) and not (
        qualified_landing_visible(obs.ocr_text)
        and not visible_exact_label(obs.ocr_text, list(LANDING_CTA_LABELS) + ["Continue", "Next"])
        and not visible_progression_label(obs.ocr_text)
    ):
        if not info_page_needs_scroll(obs):
            return None
    key = question_fingerprint(obs) or semantic_screen_signature(obs)
    used = _INFO_SCROLLS.get(key, 0)
    if used >= 8:
        logger.warning("[INFO PAGE] Scroll budget exhausted; tapping a lower-screen Continue guess.")
        coords = visual_progression_coords(obs)
        return {
            "screen_state": obs.screen_phase,
            "question_text": "",
            "answer_reason": "Info page was scrolled; tapping a lower-screen Continue control.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Continue »",
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": None,
            "kb_key": None,
            "kb_write": False,
            "missing_fact_key": None,
            "confidence_score": 0.8,
            "postcondition": "screen changed",
            "visual_reasoning": "Bounded info-page scroll finished; try the visible bottom CTA.",
        }
    _INFO_SCROLLS[key] = used + 1
    sequence = (
        "scroll_down", "scroll_down", "scroll_down",
        "scroll_up", "scroll_left", "scroll_right",
        "scroll_down", "scroll_down",
    )
    action = sequence[min(used, len(sequence) - 1)]
    logger.info("[INFO PAGE] No CTA on screen; %s to reveal Continue (%s/8).", action, used + 1)
    return {
        "screen_state": obs.screen_phase,
        "question_text": "",
        "answer_reason": "No checkbox, radio, text box or Continue is visible; scroll to reveal the next action.",
        "action": action,
        "target_element_id": None,
        "target_text": None,
        "target_coords": None,
        "input_payload": None,
        "kb_key": None,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.93,
        "postcondition": "screen changed",
        "visual_reasoning": "Instruction/qualified pages hide Continue below the fold.",
        "answer_provenance": "verified",
        "source_basis": "Current-screen OCR with no grounded CTA",
        "inference_confidence": 0.93,
    }


_I_AGREE_SESSION: dict[str, Any] = {"tapped": False}


def i_agree_consent_visible(ocr_text: str) -> bool:
    blob = re.sub(r"[\s|]+", " ", str(ocr_text or "").lower())
    blob = blob.replace("l agree", "i agree").replace("1 agree", "i agree")
    if any(k in blob for k in (
        "choreograph", "no survey", "will not directly target you",
        "panel partners", "i decline",
    )):
        return True
    return "agree" in blob and "decline" in blob


def orange_cta_milli(obs: Observation, y0: float = 0.38, y1: float = 0.92) -> list[list[int]]:
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return []
    try:
        image = cv2.imread(path)
        if image is None:
            return []
        height, width = image.shape[:2]
        mask = cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2HSV), (5, 90, 140), (25, 255, 255))
        mask[: int(height * y0), :] = 0
        mask[int(height * y1):, :] = 0
        row = (mask > 0).sum(axis=1)
        bars: list[list[int]] = []
        in_bar, start, need = False, 0, int(width * 0.28)
        for y, count in enumerate(row):
            if count >= need and not in_bar:
                in_bar, start = True, y
            elif count < need and in_bar:
                in_bar = False
                if y - start < int(height * 0.010):
                    continue
                mid = (start + y) // 2
                xs = [x for x in range(0, width, 3) if mask[mid, x] > 0]
                if xs:
                    bars.append([int(((xs[0] + xs[-1]) // 2) * 1000 / width), int(mid * 1000 / height)])
        return bars[:4]
    except Exception:
        return []


def orange_consent_bars(obs: Observation) -> list[list[int]]:
    return [b for b in orange_cta_milli(obs, 0.68, 0.93)]

def i_agree_already_selected(obs: Observation) -> bool:
    return bool(_I_AGREE_SESSION.get("tapped") or any(700 <= int(b[1]) <= 830 for b in orange_consent_bars(obs)))

def i_agree_coords(obs: Observation) -> list[int]:
    path = str(obs.screenshot or "")
    if path and Path(path).exists():
        center = ocr_text_center(Path(path), "I Agree") or ocr_text_center(Path(path), "Agree")
        if center:
            x = int(center[0] * 1000 / max(1, obs.image_width))
            y = int(center[1] * 1000 / max(1, obs.image_height))
            if 680 <= y <= 840:
                logger.info("[I AGREE OCR] milli=[%s, %s]", x, y)
                return [x, y]
    for bar in orange_consent_bars(obs):
        if 700 <= int(bar[1]) <= 830:
            return [int(bar[0]), int(bar[1])]
    return [500, 776]

def i_agree_continue_coords(obs: Observation) -> list[int]:
    variants: list[list[int]] = []
    ocr = visible_continue_milli(obs)
    if ocr:
        variants.append(ocr)
    lower = [b for b in orange_consent_bars(obs) if 840 <= int(b[1]) <= 910]
    if lower:
        variants.append([int(lower[-1][0]), min(max(int(lower[-1][1]), 850), 900)])
    for fallback in ([500, 890], [500, 882], [500, 898]):
        if fallback not in variants:
            variants.append(fallback)
    miss = int(_I_AGREE_SESSION.get("continue_misses") or 0)
    pick = variants[min(miss, len(variants) - 1)]
    logger.info("[I AGREE] Continue milli=%s miss=%s variants=%s", pick, miss, variants)
    return pick

def i_agree_consent_decision(obs: Observation, incoming: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    if not i_agree_consent_visible(obs.ocr_text) and not orange_consent_bars(obs):
        return incoming
    incoming = incoming or {}
    if not i_agree_already_selected(obs):
        coords = i_agree_coords(obs)
        inc = incoming.get("target_coords")
        if isinstance(inc, list) and len(inc) == 2 and 680 <= int(inc[1]) <= 840:
            coords = [int(inc[0]), int(inc[1])]
        logger.info("[I AGREE] Tap I Agree at %s", coords)
        return {
            "screen_state": "survey_question", "action": "click", "target_text": "I Agree",
            "target_coords": coords, "coordinate_authoritative": True, "input_payload": "I Agree",
            "confidence_score": 0.97, "postcondition": "I Agree selected", "i_agree_pick": True,
            "answer_reason": "Select I Agree, then Continue.",
        }
    coords = i_agree_continue_coords(obs)
    logger.info("[I AGREE] I Agree selected; Continue at %s", coords)
    return {
        "screen_state": "survey_question", "action": "click", "target_text": "Continue",
        "target_coords": coords, "coordinate_authoritative": True, "input_payload": None,
        "confidence_score": 0.96, "postcondition": "screen changed", "i_agree_continue": True,
        "answer_reason": "I Agree is orange; tap the lower Continue bar.",
    }


def navigation_cta_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if i_agree_consent_visible(obs.ocr_text):
        return i_agree_consent_decision(obs)
    if likert_slider_question_visible(obs.ocr_text, obs.ui_nodes):
        return likert_slider_decision(obs)
    if ranking_question_visible(obs.ocr_text):
        return ranking_decision(obs)
    if looks_like_single_choice(obs.ocr_text) or "please select an answer" in re.sub(r"\s+", " ", str(obs.ocr_text or "").lower()):
        fill = single_choice_radio_decision(obs)
        if fill:
            return fill
    if start_gate_visible(obs.ocr_text):
        coords = start_button_milli(obs)
        logger.info("[LANDING ROUTER] Start! at %s", coords)
        return {
            "screen_state": "survey_landing",
            "question_text": "",
            "answer_reason": "Instruction says click Start; tap the green Start! button.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Start!",
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": None,
            "confidence_score": 0.97,
            "postcondition": "screen changed",
            "visual_reasoning": "Visible Start! CTA, not Continue and not the cookie bar.",
            "webview_click": True,
        }
    labels = list(LANDING_CTA_LABELS) + ["Continue", "Continue »", "Next", "Next »"]
    visible_label = visible_exact_label(obs.ocr_text, labels) or visible_progression_label(obs.ocr_text)
    node, node_label = exact_label_node(obs.ui_nodes, labels)
    if not node:
        for candidate in obs.ui_nodes:
            text_label = node_text(candidate)
            if text_label and is_progression_cta(text_label) and not is_forbidden_progression_target(text_label):
                node, node_label = candidate, text_label
                break
    label = visible_label or node_label
    if label and node_label != label:
        node, _ = exact_label_node(obs.ui_nodes, [label])
    if label and not visible_label:
        if not cta_node_on_screen(node, obs):
            logger.info(
                "[LANDING ROUTER] Ignoring dump-only CTA %r node=%s; not visible on screenshot.",
                label, node.get("id") if node else None,
            )
            label = None
            node = None
    coords: Optional[list[int]] = None
    coordinate_authoritative = False

    # Prefer current screenshot geometry over accessibility nodes that may
    # belong to the hidden catalog beneath a WebView overlay.
    if visible_label and obs.screenshot and Path(obs.screenshot).exists():
        center = ocr_text_center(Path(obs.screenshot), visible_label)
        if center:
            coords = [
                int(max(0, min(1000, center[0] * 1000 / max(1, obs.image_width)))),
                int(max(0, min(1000, center[1] * 1000 / max(1, obs.image_height)))),
            ]
            coordinate_authoritative = True
            node = None
    if qualified_landing_visible(obs.ocr_text) and not info_page_needs_scroll(obs):
        # Wide bottom Participate sits at ~90% of the screenshot, just above the
        # system nav. Dump-node centers look like nav-bar taps and get refused.
        vis = None
        try:
            vis = visual_progression_coords(obs)
        except Exception:
            vis = None
        if vis and 720 <= int(vis[1]) <= 930:
            y = int(vis[1])
            if y >= 890:
                y -= 30
            coords = [500, min(875, max(850, y))]
        elif not (isinstance(coords, list) and len(coords) == 2 and 850 <= int(coords[1]) <= 875):
            coords = [500, 860]
        else:
            y = int(coords[1])
            if y >= 890:
                y = min(875, y - 30)
            coords = [int(coords[0]), min(875, max(850, y))]
        label = visible_label or label or "Participate"
        node = None
        coordinate_authoritative = True
        logger.info("[THINK] SEE green Participate THEREFORE tap pill center %s (above Android nav)", coords)
    if label:
        logger.info(
            "[LANDING ROUTER] CTA=%r node=%s coords=%s screenshot_grounded=%s",
            label, node.get("id") if node else None, coords, coordinate_authoritative,
        )
        return {
            "screen_state": obs.screen_phase,
            "question_text": "",
            "answer_reason": "Advance through the survey landing screen.",
            "action": "click",
            "target_element_id": node.get("id") if node else None,
            "target_text": label,
            "target_coords": coords,
            "coordinate_authoritative": coordinate_authoritative,
            "input_payload": None,
            "kb_key": None,
            "kb_write": False,
            "missing_fact_key": None,
            "confidence_score": 0.95,
            "postcondition": "screen changed",
            "visual_reasoning": f"Standalone navigation CTA is visible: {label}",
            "answer_provenance": "verified",
            "source_basis": "Current UI/OCR line geometry",
            "inference_confidence": 0.95,
        }
    scrolled = scroll_until_cta_decision(obs)
    if scrolled:
        return scrolled
    return None


def consent_overlay_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Resolve a visible cookie overlay before touching controls behind it."""
    if not cookie_consent_visible(obs.ocr_text, obs.ui_nodes):
        return None
    action = COOKIE_CONSENT_ACTION if COOKIE_CONSENT_ACTION in {"accept", "reject"} else "accept"
    labels = (
        ("Accept all", "Allow all", "Accept", "Agree")
        if action == "accept"
        else ("Reject all", "Reject", "Decline")
    )
    node, node_label = exact_label_node(obs.ui_nodes, labels)
    label = node_label or visible_exact_label(obs.ocr_text, labels)
    if not label:
        # Strong overlay detection permits a sparse-text OCR retry during
        # execution. Use the shortest provider-neutral label for that retry.
        label = "Accept" if action == "accept" else "Reject"
    logger.info(
        "[CONSENT ROUTER] Cookie overlay action=%s node=%s text=%r",
        action, node.get("id") if node else None, label,
    )
    return {
        "screen_state": "consent_overlay",
        "question_text": "",
        "answer_reason": f"Resolve the blocking cookie overlay using configured action: {action}.",
        "action": "click",
        "target_element_id": node.get("id") if node else None,
        "target_text": label,
        "target_coords": None,
        "input_payload": None,
        "kb_key": None,
        "kb_write": False,
        "missing_fact_key": None,
        "confidence_score": 0.99,
        "postcondition": "cookie overlay dismissed",
        "visual_reasoning": "Cookie controls cover the survey; the overlay must be resolved first.",
        "answer_provenance": "verified",
        "source_basis": "Current visible cookie-overlay OCR/UI",
        "inference_confidence": 0.99,
    }


def permission_dialog_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Apply the configured permission policy without silently granting sensitive access."""
    if not permission_dialog_visible(obs.ocr_text, obs.ui_nodes):
        return None
    text = re.sub(r"\s+", " ", obs.ocr_text.lower())
    category = "unknown"
    allowed = False
    if any(term in text for term in ("camera", "take pictures", "record video")):
        category, allowed = "camera", ALLOW_CAMERA_PERMISSION
    elif any(term in text for term in ("microphone", "record audio")):
        category, allowed = "microphone", ALLOW_MICROPHONE_PERMISSION
    elif any(term in text for term in ("location", "precise location", "nearby")):
        category, allowed = "location", ALLOW_LOCATION_PERMISSION
    elif any(term in text for term in ("photos", "media", "files", "documents")):
        category, allowed = "files", ALLOW_FILES_PERMISSION
    elif "notification" in text:
        category, allowed = "notifications", True
    if PERMISSION_POLICY == "allow_all":
        allowed = True
    elif PERMISSION_POLICY == "deny_all":
        allowed = False

    labels = (
        ("While using the app", "Only this time", "Allow", "Allow all")
        if allowed else
        ("Don't allow", "Don’t allow", "Deny", "Not now", "Cancel")
    )
    node, node_label = exact_label_node(obs.ui_nodes, labels)
    label = node_label or visible_exact_label(obs.ocr_text, labels)
    if not label:
        return {
            "screen_state": "permission_dialog", "action": "request_human",
            "target_element_id": None, "target_text": None, "target_coords": None,
            "input_payload": None, "kb_key": None, "kb_write": False,
            "confidence_score": 0.0,
            "postcondition": "permission decision required",
            "visual_reasoning": f"The {category} permission dialog has no safely grounded action.",
        }
    return {
        "screen_state": "permission_dialog", "question_text": "",
        "answer_reason": f"Apply configured {category} permission policy: {'allow' if allowed else 'deny'}.",
        "action": "handle_permission",
        "target_element_id": node.get("id") if node else None,
        "target_text": label, "target_coords": None, "input_payload": None,
        "kb_key": None, "kb_write": False, "missing_fact_key": None,
        "confidence_score": 0.99, "postcondition": "permission dialog dismissed",
        "visual_reasoning": "The permission category and configured policy determine the grounded button.",
        "answer_provenance": "verified", "source_basis": "Runtime permission policy",
        "inference_confidence": 0.99,
    }


def authorized_android_upload_path() -> Optional[str]:
    if not AUTHORIZED_UPLOAD_FILE:
        return None
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(AUTHORIZED_UPLOAD_FILE).name).strip("_")
    return f"/sdcard/Download/{safe_name or 'authorized_upload'}"


def android_file_exists(path: str) -> bool:
    if not path:
        return False
    result = adb(["shell", "test", "-f", path], timeout=10)
    return result.returncode == 0


def document_picker_decision(obs: Observation) -> Optional[dict[str, Any]]:
    """Select only an explicitly authorized file; never invent an upload."""
    if not document_picker_visible(obs.ocr_text, obs.ui_nodes):
        return None
    if not AUTHORIZED_UPLOAD_FILE:
        return {
            "screen_state": "document_picker", "action": "request_human",
            "target_element_id": None, "target_text": None, "target_coords": None,
            "input_payload": None, "kb_key": None, "kb_write": False,
            "confidence_score": 0.0, "postcondition": "authorized file required",
            "visual_reasoning": "Set AUTHORIZED_UPLOAD_FILE before permitting a survey upload.",
        }
    local_path = Path(AUTHORIZED_UPLOAD_FILE)
    if not local_path.is_file():
        return {
            "screen_state": "document_picker", "action": "request_human",
            "target_element_id": None, "target_text": str(local_path), "target_coords": None,
            "input_payload": None, "kb_key": None, "kb_write": False,
            "confidence_score": 0.0, "postcondition": "authorized file exists",
            "visual_reasoning": "The configured upload file does not exist on the computer.",
        }
    android_path = authorized_android_upload_path()
    filename = Path(android_path).name if android_path else local_path.name
    node = text_match_node(obs.ui_nodes, filename)
    visible = filename.lower() in obs.ocr_text.lower()
    if node or visible:
        return {
            "screen_state": "document_picker", "question_text": "",
            "answer_reason": "Select the explicitly authorized upload file.",
            "action": "pick_file", "target_element_id": node.get("id") if node else None,
            "target_text": filename, "target_coords": None, "input_payload": str(local_path),
            "kb_key": None, "kb_write": False, "missing_fact_key": None,
            "confidence_score": 0.99, "postcondition": "document picker dismissed",
            "visual_reasoning": "The configured filename is visible in the Android document picker.",
            "answer_provenance": "verified", "source_basis": "AUTHORIZED_UPLOAD_FILE",
            "inference_confidence": 0.99,
        }
    if android_path and not android_file_exists(android_path):
        return {
            "screen_state": "document_picker", "question_text": "",
            "answer_reason": "Stage the explicitly authorized file in Android Downloads.",
            "action": "stage_file", "target_element_id": None, "target_text": filename,
            "target_coords": None, "input_payload": str(local_path),
            "android_file_path": android_path,
            "kb_key": None, "kb_write": False, "missing_fact_key": None,
            "confidence_score": 0.99, "postcondition": "authorized file staged",
            "visual_reasoning": "Only the configured local file is copied to the device.",
            "answer_provenance": "verified", "source_basis": "AUTHORIZED_UPLOAD_FILE",
            "inference_confidence": 0.99,
        }
    return None


def terminal_survey_modal_visible(obs: Observation) -> bool:
    combined = " ".join(
        [obs.ocr_text] + [node_text(node) for node in obs.ui_nodes if node_text(node)]
    ).lower()
    combined = re.sub(r"\s+", " ", combined)
    return any(term in combined for term in TERMINAL_SURVEY_PHRASES)


def top_left_close_node(obs: Observation) -> Optional[dict[str, Any]]:
    """Find an accessible Close/X control in the modal's top-left region."""
    labeled: list[dict[str, Any]] = []
    geometric: list[dict[str, Any]] = []
    for node in obs.ui_nodes:
        if not node.get("enabled") or not node.get("clickable"):
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4:
            continue
        x1, y1, x2, y2 = [int(value) for value in bounds]
        if x2 <= x1 or y2 <= y1:
            continue
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        if center_x > obs.image_width * 0.30 or center_y > obs.image_height * 0.22:
            continue
        descriptor = " ".join(
            str(node.get(key) or "")
            for key in ("text", "content_desc", "resource_id", "class")
        ).lower()
        if any(term in descriptor for term in ("close", "dismiss", "cancel")):
            labeled.append(node)
        else:
            geometric.append(node)
    candidates = labeled or geometric
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda node: (
            node_center(node)[0] / max(1, obs.image_width)
            + node_center(node)[1] / max(1, obs.image_height)
        ),
    )


def terminal_action_button(obs: Observation) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Prefer an explicit modal action such as Okay over a corner close icon."""
    normalized_ocr = re.sub(r"\s+", " ", obs.ocr_text.lower())
    for label in ("Okay", "OK", "Done", "Return", "Close", "Continue"):
        node = text_match_node(obs.ui_nodes, label)
        if node:
            bounds = node.get("bounds") or []
            if len(bounds) != 4 or (bounds[1] + bounds[3]) / 2 >= obs.image_height * 0.45:
                return node, label
        if re.search(rf"\b{re.escape(label.lower())}\b", normalized_ocr):
            return None, label
    if any(
        phrase in normalized_ocr
        for phrase in ("didn't qualify", "did not qualify", "didn’t qualify", "not eligible")
    ):
        # This app's disqualification outcome always exposes a wide bottom Okay
        # button, which whole-page OCR may omit because it is near the nav bar.
        return None, "Okay"
    return None, None


def close_survey_confirm_visible(obs: Observation) -> bool:
    text = re.sub(r"\s+", " ", str(obs.ocr_text or "").lower())
    return "close this survey" in text or (
        "cannot open it again" in text and "go back" in text
    )


def close_survey_confirm_decision(obs: Observation) -> dict[str, Any]:
    """Never exit a live survey from the X confirm dialog. Tap GO BACK."""
    node = text_match_node(obs.ui_nodes, "GO BACK") or text_match_node(obs.ui_nodes, "Go back")
    coords = [320, 520]
    if obs.screenshot and Path(obs.screenshot).exists():
        center = ocr_text_center(Path(obs.screenshot), "GO BACK")
        if center:
            coords = [
                int(max(80, min(500, center[0] * 1000 / max(1, obs.image_width)))),
                int(max(280, min(800, center[1] * 1000 / max(1, obs.image_height)))),
            ]
    logger.info("[CLOSE CONFIRM] Tapping GO BACK; never CLOSE SURVEY.")
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": "Close-survey confirm is a mistake. GO BACK to the question.",
        "action": "click",
        "target_element_id": node.get("id") if node else None,
        "target_text": "GO BACK",
        "target_coords": coords,
        "coordinate_authoritative": True,
        "kb_write": False,
        "confidence_score": 0.99,
        "postcondition": "screen changed",
        "visual_reasoning": "The dialog asks to abandon the survey; cancel it.",
        "answer_provenance": "verified",
        "source_basis": "Close-this-survey confirm dialog",
        "inference_confidence": 0.99,
        "terminal_close": False,
    }


def authorize_grounded_terminal_close(
    decision: dict[str, Any], obs: Observation
) -> dict[str, Any]:
    """Validate/repair terminal exit intent and ground the safest visible control."""
    if close_survey_confirm_visible(obs):
        return close_survey_confirm_decision(obs)
    if not terminal_survey_modal_visible(obs):
        return decision

    intent_text = " ".join(
        str(decision.get(key) or "")
        for key in (
            "screen_state", "action", "target_text", "answer_reason",
            "postcondition", "visual_reasoning", "source_basis",
        )
    ).lower()
    action = str(decision.get("action") or "").lower()
    action_node, action_label = terminal_action_button(obs)
    close_intent = (
        action in {"back", "click"}
        and any(
            term in intent_text
            for term in ("close", "exit", "dismiss", "cross", "okay", " ok ", "done", " x ")
        )
    )
    # A prominent explicit terminal button is safe to use even if the model
    # returned wait/finish or omitted a meaningful confidence score.
    if not action_label and not close_intent:
        return decision

    target = action_node or top_left_close_node(obs)
    target_text = action_label or (node_text(target) if target else "")
    if action_label:
        fallback_coords = [500, 900]
        route = f"prominent {action_label} button"
    else:
        fallback_coords = [65, 55]
        route = "top-left Close/X control"
    logger.info(
        "[TERMINAL MODAL] Grounded exit via %s node=%s text=%r coords=%s",
        route,
        target.get("id") if target else None,
        target_text,
        None if target else fallback_coords,
    )
    return {
        **decision,
        "screen_state": "terminal_modal",
        "action": "click",
        "target_element_id": target.get("id") if target else None,
        "target_text": target_text or None,
        "target_coords": None if target else fallback_coords,
        "input_payload": None,
        "confidence_score": 0.98 if target else 0.90,
        "postcondition": "screen changed",
        "visual_reasoning": (
            "The terminal survey outcome was validated against current OCR/UI and "
            f"grounded to the {route}."
        ),
        "answer_provenance": "verified",
        "source_basis": "LLM decision plus current terminal-modal OCR/UI grounding",
        "inference_confidence": 0.98 if target else 0.90,
        "terminal_close": True,
    }
