# 20b_screen_objects.py — screenshot/UI/OCR scene graph and safe target grounding

_SCREEN_OBJECT_CACHE: dict[str, dict[str, Any]] = {}

_ACTION_WORDS = (
    "accept", "agree", "allow", "apply", "back", "begin", "complete",
    "confirm", "continue", "done", "finish", "get started", "next", "no",
    "okay", "ok", "participate", "proceed", "save", "start", "submit", "yes",
)


def _box_iou(left: list[int], right: list[int]) -> float:
    x1, y1 = max(left[0], right[0]), max(left[1], right[1])
    x2, y2 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if not intersection:
        return 0.0
    la = max(1, (left[2] - left[0]) * (left[3] - left[1]))
    ra = max(1, (right[2] - right[0]) * (right[3] - right[1]))
    return intersection / max(1, la + ra - intersection)


def _box_contains(box: list[int], x: int, y: int, pad: int = 0) -> bool:
    return box[0] - pad <= x <= box[2] + pad and box[1] - pad <= y <= box[3] + pad


def _box_to_milli(box: list[int], width: int, height: int) -> tuple[list[int], list[int]]:
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    return [cx, cy], [int(cx * 1000 / width), int(cy * 1000 / height)]


def _clean_control_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _is_action_label(value: str) -> bool:
    label = _clean_control_label(value)
    if not label or len(label) > 48:
        return False
    return any(label == word or label.startswith(word + " ") for word in _ACTION_WORDS)


def _ocr_scene_lines(obs: Observation) -> list[dict[str, Any]]:
    if not obs.screenshot:
        return []
    path = Path(str(obs.screenshot or ""))
    if not path.exists():
        return []
    found: list[dict[str, Any]] = []
    for psm in (11, 6):
        try:
            lines = ocr_line_nodes(path, psm=psm)
        except Exception as exc:
            logger.debug("[SCREEN MAP] OCR psm=%s unavailable: %s", psm, exc)
            continue
        for line in lines:
            bounds = line.get("bounds")
            label = node_text(line).strip()
            if not label or not isinstance(bounds, list) or len(bounds) != 4:
                continue
            if any(
                _clean_control_label(label) == _clean_control_label(item["label"])
                and _box_iou([int(v) for v in bounds], item["bounds"]) > 0.45
                for item in found
            ):
                continue
            found.append({"label": label, "bounds": [int(v) for v in bounds]})
    return found


def _navigation_top_from_pixels(image: Any) -> int:
    """Return the first system-navigation row in milli coordinates.

    The fallback is 945, not the old 860/920 guesses. We only accept a strong
    full-width row transition in the final 6% of the screenshot. This avoids
    confusing the lower edge of a bottom CTA (normally near 92.5%) with nav.
    """
    if image is None:
        return 945
    height, width = image.shape[:2]
    if height < 100 or width < 100:
        return 945
    strip = image[:, int(width * 0.08): int(width * 0.92)]
    medians = np.median(strip, axis=1).astype(np.float32)
    deltas = np.linalg.norm(medians[1:] - medians[:-1], axis=1)
    start, stop = int(height * 0.940), int(height * 0.985)
    candidates = [row + 1 for row in range(start, stop) if deltas[row] >= 6.0]
    if not candidates:
        return 945
    # Prefer the strongest transition, but never claim navigation begins above 94%.
    row = max(candidates, key=lambda value: float(deltas[value - 1]))
    return max(940, min(985, int(row * 1000 / height)))


def _visual_regions(obs: Observation, lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    if not obs.screenshot:
        return [], 945
    path = Path(str(obs.screenshot or ""))
    image = cv2.imread(str(path)) if path.exists() else None
    if image is None:
        return [], 945
    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    candidates: list[dict[str, Any]] = []

    def add_box(box: list[int], source: str, color: str, confidence: float) -> None:
        x1, y1, x2, y2 = box
        bw, bh = x2 - x1, y2 - y1
        if bw < int(width * 0.035) or bh < int(height * 0.009):
            return
        if y1 < int(height * 0.025) or y2 > int(height * 0.986):
            return
        if y1 >= int(height * 0.55) and source == "opencv-shape":
            return
        for current in candidates:
            if _box_iou(box, current["bounds"]) > 0.82:
                if confidence > current["confidence"]:
                    current.update({"bounds": box, "source": source, "color": color,
                                    "confidence": confidence})
                return
        labels: list[str] = []
        pad_x, pad_y = int(width * 0.018), int(height * 0.008)
        for line in lines:
            lb = line["bounds"]
            lx, ly = (lb[0] + lb[2]) // 2, (lb[1] + lb[3]) // 2
            if _box_contains(box, lx, ly, max(pad_x, pad_y)):
                labels.append(line["label"])
        label = " ".join(dict.fromkeys(labels)).strip()
        aspect = bw / max(1, bh)
        if y1 < int(height * 0.22) and color == "green" and not _is_action_label(label):
            role = "label"
        elif _is_action_label(label) or (aspect >= 3.0 and color != "neutral"):
            role = "button"
        elif 0.70 <= aspect <= 1.40 and bw <= int(width * 0.15):
            role = "choice"
        elif aspect >= 2.4 and color == "neutral":
            role = "input_or_listbox"
        else:
            role = "visual_region"
        center, milli = _box_to_milli(box, width, height)
        candidates.append({
            "id": None, "label": label, "role": role, "kind": role,
            "bounds": box, "center": center, "milli": milli,
            "grid": [min(5, int(center[0] * 6 / width)),
                     min(9, int(center[1] * 10 / height))],
            "source": source, "confidence": confidence, "color": color,
            "clickable": role in {"button", "choice", "input_or_listbox"},
            "enabled": True,
        })

    # Filled/saturated controls: CTA buttons, selected options and colored widgets.
    masks = (
        ("green", cv2.inRange(hsv, (32, 55, 35), (100, 255, 255))),
        ("blue", cv2.inRange(hsv, (90, 55, 45), (135, 255, 255))),
        ("orange", cv2.inRange(hsv, (5, 70, 70), (28, 255, 255))),
        ("purple", cv2.inRange(hsv, (130, 40, 45), (175, 255, 255))),
    )
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, width // 220), max(3, height // 500)))
    for color, mask in masks:
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for index in range(1, count):
            x, y, bw, bh, area = [int(value) for value in stats[index]]
            if area < max(350, int(width * height * 0.00035)):
                continue
            fill = area / max(1, bw * bh)
            if fill < 0.18:
                continue
            add_box([x, y, x + bw, y + bh], "opencv-color", color, min(0.96, 0.76 + fill * 0.20))

    # Neutral outlined controls: text boxes, dropdowns, list boxes and radio/checkbox outlines.
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 55, 150)
    edge_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, edge_kernel, iterations=2)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        aspect = bw / max(1, bh)
        if bw * bh < int(width * height * 0.0004):
            continue
        plausible = (
            (bw >= int(width * 0.28) and int(height * 0.018) <= bh <= int(height * 0.22))
            or (0.65 <= aspect <= 1.45 and int(width * 0.025) <= bw <= int(width * 0.16))
        )
        if plausible:
            add_box([x, y, x + bw, y + bh], "opencv-shape", "neutral", 0.72)

    return candidates, _navigation_top_from_pixels(image)


def build_screen_object_map(obs: Observation, persist: bool = False) -> dict[str, Any]:
    """Build a graph of paragraphs and interactive objects for the current screen."""
    cache_key = f"{obs.screen_hash}:{obs.image_width}x{obs.image_height}:{len(obs.ui_nodes)}"
    if cache_key in _SCREEN_OBJECT_CACHE:
        scene = _SCREEN_OBJECT_CACHE[cache_key]
        if persist:
            persist_screen_object_map(obs, scene)
        return scene
    width = max(1, int(obs.image_width or obs.device_width or 1))
    height = max(1, int(obs.image_height or obs.device_height or 1))
    lines = _ocr_scene_lines(obs)
    controls: list[dict[str, Any]] = []
    for item in map_form_controls(obs):
        kind = str(item.get("kind") or "unknown")
        role = {
            "choice": "choice", "dropdown": "dropdown", "text_input": "text_input",
            "button": "button", "label": "label",
        }.get(kind, kind)
        controls.append({**item, "role": role, "color": "semantic"})

    visual, nav_top = _visual_regions(obs, lines)
    for candidate in visual:
        duplicate = next((
            item for item in controls
            if _box_iou(candidate["bounds"], item["bounds"]) > 0.55
            or (
                candidate.get("label") and item.get("label")
                and _clean_control_label(candidate["label"]) == _clean_control_label(item["label"])
                and abs(candidate["center"][1] - item["center"][1]) < int(height * 0.04)
            )
        ), None)
        if duplicate:
            if candidate.get("label") and not duplicate.get("label"):
                duplicate["label"] = candidate["label"]
            duplicate["confidence"] = max(float(duplicate.get("confidence") or 0), candidate["confidence"])
            duplicate["visual_bounds"] = candidate["bounds"]
            duplicate["visual_center"] = candidate["center"]
            duplicate["visual_milli"] = candidate["milli"]
            duplicate["color"] = candidate["color"]
            duplicate["source"] = f"{duplicate.get('source')}+{candidate['source']}"
            if candidate["role"] == "button":
                duplicate["role"] = "button"
        else:
            controls.append(candidate)

    interactive = [item for item in controls if item.get("role") != "label" or item.get("clickable")]
    paragraphs: list[dict[str, Any]] = []
    for line in lines:
        label = line["label"].strip()
        if len(label) < 18 or _is_action_label(label):
            continue
        x1, y1, x2, y2 = line["bounds"]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if any(_box_contains(item["bounds"], cx, cy, 2) for item in interactive):
            continue
        paragraphs.append({"text": label, "bounds": line["bounds"]})

    controls.sort(key=lambda item: (item["center"][1], item["center"][0]))
    scene = {
        "screen_hash": obs.screen_hash, "image_size": [width, height],
        "navigation_top_milli": nav_top, "controls": controls,
        "paragraphs": paragraphs,
    }
    if len(_SCREEN_OBJECT_CACHE) >= 16:
        _SCREEN_OBJECT_CACHE.pop(next(iter(_SCREEN_OBJECT_CACHE)))
    _SCREEN_OBJECT_CACHE[cache_key] = scene
    logger.info(
        "[SCREEN MAP] controls=%s interactive=%s paragraphs=%s nav_top=%s",
        len(controls), len(interactive), len(paragraphs), nav_top,
    )
    if persist:
        persist_screen_object_map(obs, scene)
    return scene


def find_screen_control(
    obs: Observation,
    target_text: str,
    expected_role: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    wanted = _clean_control_label(target_text)
    if not wanted:
        return None
    scene = build_screen_object_map(obs)
    candidates: list[tuple[float, dict[str, Any]]] = []
    for item in scene["controls"]:
        label = _clean_control_label(item.get("label") or "")
        if not label:
            continue
        score = 0.0
        if label == wanted:
            score += 8.0
        elif wanted in label or label in wanted:
            score += 5.0
        else:
            common = set(wanted.split()) & set(label.split())
            score += len(common) * 1.2
        if expected_role and item.get("role") == expected_role:
            score += 2.0
        if _is_action_label(target_text) and item.get("role") == "button":
            score += 2.0
        if "opencv" in str(item.get("source") or "") or item.get("visual_milli"):
            score += 2.0
        if int(item.get("milli", [0, 0])[1]) >= int(scene.get("navigation_top_milli") or 945):
            score -= 8.0
        if "participate" in wanted:
            if item.get("color") == "green":
                score += 4.0
            if item["milli"][1] >= 700:
                score += 1.0
        if "submit" in wanted or "continue" in wanted or "next" in wanted:
            y = int(item.get("milli", [0, 0])[1])
            if y < 150:
                score -= 20.0
            if y < 500:
                score -= 12.0
            if 700 <= y <= 920:
                score += 8.0
            if item.get("color") == "green" and 300 <= y <= 700:
                score += 6.0
            if y >= 930:
                score -= 8.0
        score += float(item.get("confidence") or 0)
        if score >= 4.0:
            candidates.append((score, item))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: (pair[0], pair[1]["milli"][1]), reverse=True)
    return candidates[0][1]


def _decision_control(decision: dict[str, Any], obs: Observation) -> Optional[dict[str, Any]]:
    target = str(decision.get("target_text") or "").strip()
    expected = "button" if _is_action_label(target) else None
    control = find_screen_control(obs, target, expected) if target else None
    if control:
        return control
    coords = decision.get("target_coords")
    if isinstance(coords, (list, tuple)) and len(coords) >= 2:
        try:
            mx, my = int(coords[0]), int(coords[1])
        except (TypeError, ValueError):
            return None
        scene = build_screen_object_map(obs)
        for item in scene["controls"]:
            b = item["bounds"]
            px = int(mx * scene["image_size"][0] / 1000)
            py = int(my * scene["image_size"][1] / 1000)
            if _box_contains(b, px, py) and item.get("clickable"):
                return item
    return None


def screen_control_retry_points(control: dict[str, Any], failed: set[tuple[int, int]]) -> list[list[int]]:
    milli = list(control.get("visual_milli") or control.get("milli") or [])
    bounds = control.get("visual_bounds") or control.get("bounds") or []
    if len(milli) != 2 or len(bounds) != 4:
        return []
    width = max(1, int(control.get("scene_width") or 1000))
    height = max(1, int(control.get("scene_height") or 1000))
    # Bounds are pixels. Derive small offsets in milli but keep every retry inside.
    half_w = max(8, int((bounds[2] - bounds[0]) * 1000 / width / 5))
    half_h = max(6, int((bounds[3] - bounds[1]) * 1000 / height / 5))
    raw = [
        milli, [milli[0], milli[1] + half_h], [milli[0], milli[1] - half_h],
        [milli[0] - half_w, milli[1]], [milli[0] + half_w, milli[1]],
    ]
    return [[int(x), int(y)] for x, y in raw if (int(x), int(y)) not in failed]


def ground_decision_to_screen_map(decision: dict[str, Any], obs: Observation) -> dict[str, Any]:
    """Replace guesses with a detected control centre and retain its exact bounds."""
    if not decision:
        return decision
    action = str(decision.get("action") or "").lower()
    if action not in {
        "click", "select_option", "toggle_checkbox", "open_dropdown",
        "select_dropdown", "open_date_picker", "open_time_picker", "long_press",
    }:
        return decision
    control = _decision_control(decision, obs)
    if not control or float(control.get("confidence") or 0) < 0.70:
        return decision
    if decision.get("skip_object_grounding") or str(decision.get("kb_key") or "") == "age":
        wanted_label = _clean_control_label(str(decision.get("target_text") or ""))
        if action == "click" and wanted_label in {"arrow", "continue", "go", "next"}:
            milli = list((control.get("visual_milli") or control.get("milli") or [0, 0]))
            if len(milli) < 2 or int(milli[1]) < 400 or abs(int(milli[0]) - 500) > 220:
                logger.info("[OBJECT GROUNDING] Keeping age/arrow coords; rejected %s", milli)
                return decision
    wanted = _clean_control_label(str(decision.get("target_text") or ""))
    cy = int((control.get("visual_milli") or control.get("milli") or [0, 0])[1])
    if wanted in {"submit", "continue", "next"} and (cy < 150 or cy > 720):
        return decision
    scene = build_screen_object_map(obs)
    control = dict(control)
    control["scene_width"], control["scene_height"] = scene["image_size"]
    failed = failed_coords_set() if "failed_coords_set" in globals() else set()
    points = screen_control_retry_points(control, failed)
    if not points:
        points = [list(control.get("visual_milli") or control["milli"])]
    out = dict(decision)
    out["target_coords"] = points[0]
    out["target_bounds"] = list(control.get("visual_bounds") or control["bounds"])
    out["target_control_role"] = control.get("role")
    out["target_control_source"] = control.get("source")
    out["control_confidence"] = round(float(control.get("confidence") or 0), 3)
    out["coordinate_authoritative"] = True
    out["object_map_grounded"] = True
    logger.info(
        "[OBJECT GROUNDING] %r role=%s bounds=%s milli=%s confidence=%.3f",
        out.get("target_text"), control.get("role"), out["target_bounds"],
        out["target_coords"], float(control.get("confidence") or 0),
    )
    return out


def safe_navigation_top_milli(obs: Observation) -> int:
    try:
        return int(build_screen_object_map(obs).get("navigation_top_milli") or 945)
    except Exception:
        return 945


def persist_screen_object_map(obs: Observation, scene: dict[str, Any]) -> None:
    if not SAVE_SCREEN_MAPS or not obs.screenshot:
        return
    path = Path(str(obs.screenshot))
    image = cv2.imread(str(path)) if path.exists() else None
    if image is None:
        return
    try:
        role_colors = {
            "button": (0, 180, 0), "choice": (0, 160, 255),
            "dropdown": (255, 130, 0), "text_input": (255, 0, 160),
            "input_or_listbox": (255, 0, 160), "visual_region": (160, 160, 0),
        }
        for index, item in enumerate(scene["controls"]):
            if item.get("role") == "label" and not item.get("clickable"):
                continue
            x1, y1, x2, y2 = [int(value) for value in item["bounds"]]
            color = role_colors.get(str(item.get("role")), (120, 120, 120))
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
            caption = f"{index}:{item.get('role')} {str(item.get('label') or '')[:28]}"
            cv2.putText(image, caption, (max(2, x1), max(18, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
        nav_y = int(image.shape[0] * int(scene["navigation_top_milli"]) / 1000)
        cv2.line(image, (0, nav_y), (image.shape[1] - 1, nav_y), (0, 0, 255), 3)
        cv2.imwrite(str(SCREENSHOT_DIR / "_screen_map_latest.png"), image)
        payload = {
            "screen_hash": scene["screen_hash"], "image_size": scene["image_size"],
            "navigation_top_milli": scene["navigation_top_milli"],
            "controls": scene["controls"], "paragraphs": scene["paragraphs"],
        }
        (SCREENSHOT_DIR / "_screen_map_latest.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        logger.debug("[SCREEN MAP] Could not persist latest map: %s", exc)


def screen_object_map_regression_self_check() -> bool:
    obs = Observation(
        step=0, screenshot=None, image_width=1440, image_height=3088,
        device_width=1440, device_height=3088, screen_hash="participate-object-fixture",
        ocr_text="You've qualified for this survey!\nParticipate",
        ui_nodes=[{
            "id": 7, "text": "Participate", "content_desc": "", "class": "android.widget.Button",
            "resource_id": "", "bounds": [60, 2695, 1380, 2860], "clickable": True,
            "editable": False, "enabled": True, "checkable": False,
        }],
        kb={}, persona={}, screen_phase="survey_landing", survey_tiles=[],
    )
    raw = {"action": "click", "target_text": "Participate", "target_coords": [500, 835]}
    grounded = ground_decision_to_screen_map(raw, obs)
    point = grounded.get("target_coords") or [0, 0]
    passed = bool(
        grounded.get("object_map_grounded")
        and 890 <= int(point[1]) <= 910
        and grounded.get("target_bounds") == [60, 2695, 1380, 2860]
    )
    if passed:
        logger.info("[SELF-CHECK] Screen-object map grounds Participate inside its real bounds: %s", point)
    else:
        logger.error("[SELF-CHECK] Screen-object map failed: %s", grounded)
    return passed
