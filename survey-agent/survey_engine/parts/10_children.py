# 10_children.py — shared engine namespace (do not import directly)



def children_count_question_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    return any(token in blob for token in (
        "dependent children", "how many children", "children (under 18)",
        "children under 18", "number of children",
    ))


def child_ages_question_visible(ocr_text: str) -> bool:
    blob = re.sub(r"\s+", " ", str(ocr_text or "").lower())
    if children_count_question_visible(ocr_text):
        return False
    if re.search(r"what is your age|how old are you", blob):
        return False
    if any(token in blob for token in (
        "state their ages", "their ages", "child's age", "childs age",
        "children's ages", "ages of your", "age of your child",
    )):
        return True
    return False


def numeric_radio_labels(obs: Observation) -> list[str]:
    found: list[str] = []
    height = max(1, int(obs.image_height or obs.device_height or 1))

    def add(raw: str, cy: Optional[float] = None) -> None:
        label = re.sub(r"\s+", "", str(raw or ""))
        if not re.fullmatch(r"\d{1,2}", label):
            return
        if int(label) > 15:
            return
        if cy is not None and (cy < 0.18 or cy > 0.95):
            return
        if label not in found:
            found.append(label)

    for node in obs.ui_nodes or []:
        bounds = node.get("bounds") or []
        cy = None
        if len(bounds) == 4:
            cy = ((int(bounds[1]) + int(bounds[3])) / 2) / height
        add(node_text(node), cy)
    for line in str(obs.ocr_text or "").splitlines():
        add(line.strip())
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        try:
            for node in ocr_line_nodes(Path(obs.screenshot), psm=11):
                bounds = node.get("bounds") or []
                cy = None
                if len(bounds) == 4:
                    cy = ((int(bounds[1]) + int(bounds[3])) / 2) / height
                add(node_text(node), cy)
        except Exception as exc:
            logger.debug("Numeric radio OCR: %s", exc)
    found.sort(key=lambda item: int(item))
    if children_count_question_visible(obs.ocr_text) and len(found) < 3:
        found = [str(n) for n in range(0, 11)]
    return found


def continue_button_on_screen(obs: Observation) -> Optional[tuple[list[int], str]]:
    """Lowest Continue/Next on screen, including the sticky footer (~y=0.90)."""
    height = max(1, int(obs.image_height or obs.device_height or 1))
    width = max(1, int(obs.image_width or obs.device_width or 1))
    labels = ("Continue »", "Continue", "Next »", "Next")
    hits: list[tuple[list[int], str]] = []
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        for label in labels:
            hit = ocr_text_center(Path(obs.screenshot), label)
            if not hit:
                continue
            yf = hit[1] / height
            if 0.48 <= yf <= 0.96:
                hits.append((
                    [
                        int(max(80, min(920, hit[0] * 1000 / width))),
                        int(max(500, min(940, hit[1] * 1000 / height))),
                    ],
                    label,
                ))
    for node in obs.ui_nodes or []:
        text = node_text(node)
        if not text or not is_progression_cta(text):
            continue
        if not cta_node_on_screen(node, obs):
            continue
        cx, cy = node_center(node)
        yf = cy / height
        if yf > 0.96:
            continue
        hits.append((
            [
                int(max(80, min(920, cx * 1000 / width))),
                int(max(500, min(940, cy * 1000 / height))),
            ],
            text,
        ))
    if hits:
        hits.sort(key=lambda item: item[0][1])
        return hits[-1]
    bars = orange_cta_milli(obs, 0.84, 0.98)
    if bars:
        return [500, max(int(b[1]) for b in bars)], "Continue"
    return None


def children_continue_decision(obs: Observation, wanted: str) -> dict[str, Any]:
    found = continue_button_on_screen(obs)
    if found:
        coords, label = found
        logger.info("[CHILDREN] Continue visible at %s label=%r", coords, label)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Children count {wanted} is selected; Continue is on screen.",
            "action": "click",
            "target_element_id": None,
            "target_text": label or "Continue »",
            "target_coords": coords,
            "coordinate_authoritative": True,
            "input_payload": wanted,
            "kb_key": "number_of_children",
            "confidence_score": 0.96,
            "postcondition": "screen changed",
            "selection_complete": True,
        }
    sig = semantic_screen_signature(obs)
    used = _CHILDREN_SCROLLS.get(sig, 0)
    if used < 6:
        _CHILDREN_SCROLLS[sig] = used + 1
        logger.info("[CHILDREN] Continue not on screen; scroll_down (%s/6).", used + 1)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"Children {wanted} selected; scroll until Continue is visible.",
            "action": "scroll_down",
            "target_element_id": None,
            "target_text": None,
            "target_coords": [500, 620],
            "coordinate_authoritative": True,
            "input_payload": wanted,
            "kb_key": "number_of_children",
            "confidence_score": 0.95,
            "postcondition": "screen changed",
            "selection_complete": True,
        }
    logger.warning("[CHILDREN] Scroll budget used; tapping content-band Continue guess.")
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"Children {wanted} selected; tapping lower-content Continue.",
        "action": "click",
        "target_element_id": None,
        "target_text": "Continue »",
        "target_coords": [500, 820],
        "coordinate_authoritative": True,
        "input_payload": wanted,
        "kb_key": "number_of_children",
        "confidence_score": 0.8,
        "postcondition": "screen changed",
        "selection_complete": True,
    }


def numeric_radio_coords(obs: Observation, wanted: str) -> Optional[list[int]]:
    height = max(1, int(obs.image_height or obs.device_height or 1))
    width = max(1, int(obs.image_width or obs.device_width or 1))
    wanted_s = str(wanted).strip()
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        for psm in (6, 11):
            for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                if re.sub(r"\s+", "", node_text(node)) != wanted_s:
                    continue
                cx, cy = node_center(node)
                yf = cy / height
                if yf < 0.32 or yf > 0.88:
                    continue
                nx = int(max(70, min(220, (cx - 70) * 1000 / width)))
                ny = int(max(300, min(860, cy * 1000 / height)))
                logger.info("[CHILDREN] OCR radio %s at milli=[%s, %s]", wanted_s, nx, ny)
                return [nx, ny]
    rows: list[tuple[int, list[int]]] = []
    for node in obs.ui_nodes or []:
        label = re.sub(r"\s+", "", node_text(node))
        if not re.fullmatch(r"\d{1,2}", label) or int(label) > 10:
            continue
        bounds = node.get("bounds") or []
        if len(bounds) != 4 or in_header_chrome(bounds, height):
            continue
        x1, y1, x2, y2 = [int(v) for v in bounds]
        cy = ((y1 + y2) / 2) / height
        if cy < 0.30 or cy > 0.90:
            continue
        rows.append((int(label), [x1, y1, x2, y2]))
    rows.sort(key=lambda item: item[1][1])
    for label, bounds in rows:
        if str(label) != wanted_s:
            continue
        x1, y1, x2, y2 = bounds
        nx = int((x1 + 48) * 1000 / width)
        ny = int(((y1 + y2) / 2) * 1000 / height)
        return [max(70, min(240, nx)), max(300, min(860, ny))]
    return None


def children_pick_complete(obs: Observation, wanted: Optional[str] = None) -> bool:
    wanted = str(wanted or kb_or_persona_value(obs, "number_of_children") or "").strip()
    if wanted.isdigit():
        wanted = str(int(wanted))
    sig = semantic_screen_signature(obs)
    if wanted and _CHILDREN_TAPPED.get(sig) == wanted:
        return True
    last = (
        _LAST_SELECT_FINGERPRINT.get(question_fingerprint(obs), "")
        or _LAST_SELECT_FINGERPRINT.get(sig, "")
    )
    if wanted and last == wanted.lower():
        return True
    if wanted and wanted.lower() in selected_option_labels(obs):
        return True
    return False


def dependent_children_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not children_count_question_visible(obs.ocr_text):
        return None
    labels = numeric_radio_labels(obs)
    raw = kb_or_persona_value(obs, "number_of_children")
    if raw in (None, "") and str(kb_or_persona_value(obs, "has_children") or "").lower() in {"no", "false", "0"}:
        raw = 0
    if raw in (None, ""):
        logger.info("[CHILDREN] No number_of_children in KB/persona; asking the operator.")
        return capture_human_answer_decision(
            obs, "How many dependent children is not in knowledge_base.json."
        )
    wanted = str(int(raw)) if str(raw).strip().lstrip("-").isdigit() else str(raw).strip()
    if children_pick_complete(obs, wanted):
        logger.info("[CHILDREN] %s already tapped; grounding Continue.", wanted)
        return children_continue_decision(obs, wanted)
    if labels and wanted not in labels:
        logger.info("[CHILDREN] KB %r is not a visible radio %s; asking the operator.", wanted, labels)
        return capture_human_answer_decision(
            obs, f"Stored number_of_children={wanted} is not on this list."
        )
    coords = numeric_radio_coords(obs, wanted)
    if not coords and labels:
        idx = labels.index(wanted) if wanted in labels else 0
        coords = [140, min(820, 500 + idx * 78)]
    logger.info("[CHILDREN] Selecting %s from knowledge_base.json:number_of_children coords=%s", wanted, coords)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"knowledge_base.json number_of_children={wanted}.",
        "action": "select_option",
        "target_element_id": None,
        "target_text": wanted,
        "target_coords": coords,
        "coordinate_authoritative": True,
        "input_payload": wanted,
        "kb_key": "number_of_children",
        "kb_write": True,
        "confidence_score": 0.97,
        "postcondition": f"selected option is {wanted}",
        "answer_provenance": "declared",
        "source_basis": "knowledge_base.json:number_of_children",
        "selection_complete": True,
    }


def child_age_field_coords(obs: Observation) -> list[int]:
    height = max(1, int(obs.image_height or obs.device_height or 1))
    width = max(1, int(obs.image_width or obs.device_width or 1))
    if obs.screenshot and Path(str(obs.screenshot)).exists():
        for psm in (6, 11):
            for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                label = re.sub(r"\s+", "", node_text(node))
                if label not in {"1", "2", "3", "4", "5"}:
                    continue
                cx, cy = node_center(node)
                yf = cy / height
                if yf < 0.28 or yf > 0.62:
                    continue
                nx = int(max(80, min(280, (cx + 40) * 1000 / width)))
                ny = int(max(320, min(620, (cy + 70) * 1000 / height)))
                logger.info("[CHILD AGE] Field under row %s milli=[%s, %s]", label, nx, ny)
                return [nx, ny]
    found = empty_rounded_input_coords(obs)
    if found:
        return found
    banner = "problems with some of the data" in (obs.ocr_text or "").lower()
    return [190, 520 if banner else 420]


def child_age_typed(obs: Observation, wanted: str = "") -> bool:
    wanted = str(wanted or kb_or_persona_value(obs, "child_age") or "").strip()
    sig = semantic_screen_signature(obs)
    if wanted and _CHILD_AGE_TYPED.get(sig) == wanted:
        return True
    blob = re.sub(r"\s+", " ", str(obs.ocr_text or ""))
    if wanted and re.search(rf"(?<!\d){re.escape(wanted)}(?!\d)", blob):
        # Row label "1" is not the typed age unless wanted is not the child index alone
        # sitting on its own line. Require the flag or an editable-looking value.
        if wanted != "1":
            return True
    return False


def resolve_child_age_value(obs: Observation) -> Optional[str]:
    """child_age from live obs, disk KB, persona, or related parent flags. Never the adult age."""
    merged: dict[str, Any] = {}
    try:
        merged.update(load_kb() or {})
    except Exception:
        pass
    if isinstance(obs.kb, dict):
        merged.update(obs.kb)
    persona_val = nested_scalar(obs.persona, "child_age") if obs.persona else None
    if persona_val not in (None, ""):
        merged["child_age"] = persona_val
    for key in ("child_age", "child_ages", "kids_age", "age_of_child"):
        raw = merged.get(key)
        if raw in (None, ""):
            continue
        text = str(raw).strip()
        if text.lstrip("-").replace(".", "", 1).isdigit():
            number = int(float(text))
            if 1 <= number <= 17:
                return str(number)
        token = text.split()[0]
        if token.isdigit() and 1 <= int(token) <= 17:
            return token
    six_to_ten = str(merged.get("parent_of_6_to_10_year_old") or "").strip().lower()
    three_to_five = str(merged.get("parent_of_3_to_5_year_old") or "").strip().lower()
    if six_to_ten in {"yes", "true", "1"}:
        return "8"
    if three_to_five in {"yes", "true", "1"}:
        return "4"
    return None


def child_age_text_decision(obs: Observation) -> Optional[dict[str, Any]]:
    if not child_ages_question_visible(obs.ocr_text):
        return None
    obs.screen_phase = "survey_question"
    try:
        disk = load_kb() or {}
        obs.kb = {**disk, **(obs.kb or {})}
    except Exception:
        obs.kb = dict(obs.kb or {})
    raw = resolve_child_age_value(obs)
    if raw in (None, ""):
        if obs.screenshot is None or not stdin_can_prompt():
            logger.info("[CHILD AGE] child_age missing; skipping terminal prompt (self-check or no TTY).")
            return None
        if "child_age" in _HUMAN_PROMPTED_KEYS:
            logger.warning("[CHILD AGE] Already asked for child_age; not reprinting the prompt.")
            return None
        logger.info("[CHILD AGE] child_age missing from KB/persona; asking the operator once.")
        return capture_human_answer_decision(
            obs, "Please state their ages — child_age is not in knowledge_base.json."
        )
    wanted = str(int(raw)) if str(raw).strip().lstrip("-").isdigit() else str(raw).strip()
    if obs.kb.get("child_age") in (None, "") and wanted.isdigit():
        update_kb(
            "child_age",
            int(wanted),
            reason="Derived child_age from knowledge_base parent-age flags / disk reload.",
            provenance="declared",
            confidence=0.9,
            question="Please state their ages",
            source_basis="knowledge_base.json child_age or parent_of_6_to_10_year_old",
        )
        obs.kb["child_age"] = int(wanted)
    if child_age_typed(obs, wanted):
        found = continue_button_on_screen(obs)
        if found:
            coords, label = found
            logger.info("[CHILD AGE] %s is in the box; Continue at %s", wanted, coords)
            return {
                "screen_state": "survey_question",
                "question_text": current_question_text(obs),
                "answer_reason": f"child_age={wanted} typed; Continue.",
                "action": "click",
                "target_element_id": None,
                "target_text": label or "Continue »",
                "target_coords": coords,
                "coordinate_authoritative": True,
                "input_payload": wanted,
                "kb_key": "child_age",
                "confidence_score": 0.96,
                "postcondition": "screen changed",
                "selection_complete": True,
            }
        logger.info("[CHILD AGE] Typed %s; Continue not in content band — still click content Continue.", wanted)
        return {
            "screen_state": "survey_question",
            "question_text": current_question_text(obs),
            "answer_reason": f"child_age={wanted} typed; tap visible Continue.",
            "action": "click",
            "target_element_id": None,
            "target_text": "Continue »",
            "target_coords": [500, 620],
            "coordinate_authoritative": True,
            "input_payload": wanted,
            "kb_key": "child_age",
            "confidence_score": 0.9,
            "postcondition": "screen changed",
            "selection_complete": True,
        }
    coords = child_age_field_coords(obs)
    logger.info("[CHILD AGE] Typing knowledge_base.json:child_age=%s at %s", wanted, coords)
    return {
        "screen_state": "survey_question",
        "question_text": current_question_text(obs),
        "answer_reason": f"knowledge_base.json child_age={wanted}.",
        "action": "type_text",
        "target_element_id": None,
        "target_text": "child age input field",
        "target_coords": coords,
        "coordinate_authoritative": True,
        "input_payload": wanted,
        "kb_key": "child_age",
        "kb_write": True,
        "confidence_score": 0.97,
        "postcondition": f"field contains {wanted}",
        "answer_provenance": "declared",
        "source_basis": "knowledge_base.json:child_age",
        "selection_complete": False,
    }
