# 22_execute.py — shared engine namespace (do not import directly)
# ------------------------------------------------------------------------------
def shell_input_text(value: str) -> str:
    # Android `input text` accepts a restricted shell-ish encoding.
    # Spaces must be represented as %s. Escape characters that commonly break
    # the command. For highly complex Unicode, request human/ADB keyboard setup.
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(" ", "%s")
        .replace("&", " and ")  # ADB-safe
        .replace("'", "")
        .replace("|", "\\|")
        .replace("<", "\\<")
        .replace(">", "\\>")
        .replace(";", "\\;")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
def type_digits(value: str) -> None:
    """WebView often ignores `input text`; digit keyevents land in the focused box."""
    for ch in str(value):
        if ch.isdigit():
            adb(["shell", "input", "keyevent", str(7 + int(ch))], timeout=10)
            time.sleep(0.14)
        else:
            adb_input_multiline(ch)
            time.sleep(0.1)


def adb_input_multiline(value: str) -> None:
    """Enter multiline comments without sending literal newline shell syntax."""
    lines = str(value).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if line:
            adb(["shell", "input", "text", shell_input_text(line)], timeout=20)
        if index < len(lines) - 1:
            adb(["shell", "input", "keyevent", "KEYCODE_ENTER"], timeout=10)


def tap_native(x: int, y: int) -> None:
    adb(["shell", "input", "tap", str(x), str(y)], timeout=15)


def webview_click(x: int, y: int) -> None:
    """Chrome WebView often ignores swipe-hold; fire tap + motionevent."""
    logger.info("[WEBVIEW CLICK] native=(%s,%s)", x, y)
    adb(["shell", "input", "tap", str(x), str(y)], timeout=15)
    time.sleep(0.05)
    adb(["shell", "input", "touchscreen", "tap", str(x), str(y)], timeout=15)
    time.sleep(0.04)
    adb(["shell", "input", "motionevent", "DOWN", str(x), str(y)], timeout=15)
    time.sleep(0.04)
    adb(["shell", "input", "motionevent", "UP", str(x), str(y)], timeout=15)


def type_into_node(node: dict[str, Any], value: str) -> None:
    x, y = node_center(node)
    tap_native(x, y)
    time.sleep(0.5)

    # Move to end and clear existing text. Repeating DEL is more portable than
    # relying on CTRL+A/meta flags, which vary across Android input implementations.
    adb(["shell", "input", "keyevent", "KEYCODE_MOVE_END"], timeout=10)
    for _ in range(24):
        adb(["shell", "input", "keyevent", "KEYCODE_DEL"], timeout=10)

    adb_input_multiline(value)
    time.sleep(0.8)


def body_option_coords(obs: Observation, label: str) -> Optional[list[int]]:
    """Milli coordinates of a radio in the question body. Never the status bar."""
    wanted = normalize_choice(label)
    if obs.screenshot and Path(obs.screenshot).exists() and wanted:
        try:
            for psm in (11, 6, 3):
                body: list[dict[str, Any]] = []
                for node in ocr_line_nodes(Path(obs.screenshot), psm=psm):
                    bounds = node.get("bounds") or []
                    if len(bounds) != 4 or in_header_chrome(bounds, obs.image_height):
                        continue
                    if in_system_nav(bounds, obs.image_height):
                        continue
                    text = normalize_choice(node_text(node))
                    if wanted == text or wanted in text or text in wanted:
                        body.append(node)
                if body:
                    best = max(
                        body,
                        key=lambda node: max(1, (node["bounds"][2] - node["bounds"][0]) * (node["bounds"][3] - node["bounds"][1])),
                    )
                    x1, y1, x2, y2 = [int(v) for v in best["bounds"]]
                    nx = int((x1 + max(28, (x2 - x1) * 0.08)) * 1000 / max(1, obs.image_width))
                    ny = int(((y1 + y2) / 2) * 1000 / max(1, obs.image_height))
                    return [max(80, min(420, nx)), max(300, min(780, ny))]
        except Exception as exc:
            logger.debug("Body option OCR unavailable: %s", exc)
    lowered = str(label or "").strip().lower()
    idx = None
    if lowered == "male" or (lowered.startswith("male") and "female" not in lowered):
        idx = 0
    elif "female" in lowered:
        idx = 1
    elif "non-binary" in lowered or "nonbinary" in lowered:
        idx = 2
    if idx is None:
        return None
    return [180, 455 + idx * 108]


def option_tap_xy(
    obs: Observation,
    node: Optional[dict[str, Any]],
    target_text: str,
) -> Optional[tuple[int, int]]:
    """Tap safely inside the full radio/checkbox row beside its visible label."""
    ocr_match = None
    if target_text and obs.screenshot and Path(obs.screenshot).exists():
        matches: list[dict[str, Any]] = []
        for psm in (11, 6, 3):
            matches.extend(ocr_line_nodes(Path(obs.screenshot), psm=psm))
        ocr_match = best_option_text_node(matches, target_text)
    # Accessibility labels are already tied to the correct WebView row.  OCR is
    # only a fallback: short partial matches such as "No" can otherwise resolve
    # to Android navigation text at the bottom of the screenshot.
    source = node or ocr_match
    if source and in_system_nav(source.get("bounds") or [], obs.image_height):
        logger.warning("[OPTION TAP] Ignoring nav-bar node bounds=%s for %r", source.get("bounds"), target_text)
        source = None
    if source and in_header_chrome(source.get("bounds") or [], obs.image_height):
        logger.warning("[OPTION TAP] Ignoring header node bounds=%s for %r", source.get("bounds"), target_text)
        source = None
    if source and isinstance(source.get("bounds"), list) and len(source["bounds"]) == 4:
        x1, y1, x2, y2 = [int(v) for v in source["bounds"]]
        width = max(1, x2 - x1)
        y = (y1 + y2) // 2
        if width <= max(180, int(obs.image_width * 0.28)):
            # Label centres are reliable WebView hit targets. A fixed 38% x
            # missed narrow radio rows and could hit another option.
            x = (x1 + x2) // 2
        else:
            x = x1 + max(28, int(width * 0.08))
        if y >= int(obs.image_height * 0.88) or y <= int(obs.image_height * 0.20):
            logger.warning("[OPTION TAP] Refusing chrome tap (%s,%s) for %r", x, y, target_text)
            source = None
        else:
            logger.info("[OPTION TAP] text=%r node_bounds=%s tap=(%s,%s)", target_text, source.get("bounds"), x, y)
            return x, y
    milli = body_option_coords(obs, target_text)
    if milli:
        native = normalized_to_native(
            milli, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
        )
        logger.info("[OPTION TAP] Body fallback text=%r milli=%s native=%s", target_text, milli, native)
        return native
    return None


def execute_action(decision: dict[str, Any], obs: Observation) -> ActionResult:
    if "ground_decision_to_screen_map" in globals() and not decision.get("skip_object_grounding"):
        decision = ground_decision_to_screen_map(decision, obs)
    action = str(decision.get("action", "")).lower().strip()
    node = node_by_id(obs.ui_nodes, decision.get("target_element_id"))
    target_text = str(decision.get("target_text") or "").strip()
    coords = decision.get("target_coords")
    gesture_start = decision.get("gesture_start")
    gesture_end = decision.get("gesture_end")
    control_value = decision.get("control_value")
    payload = decision.get("input_payload")

    logger.info(
        "[ACTION] %s | node=%s | text=%r | coords=%r | payload=%r",
        action, decision.get("target_element_id"), target_text, coords, payload
    )

    if action == "finish":
        return ActionResult(True, False, "LLM declared completion.")

    if action == "wait":
        time.sleep(0.8)
        return ActionResult(True, False, "Waited.")

    if action == "fill_date_parts":
        return execute_birth_date_action(decision, obs)

    if action == "back":
        adb(["shell", "input", "keyevent", "KEYCODE_BACK"], timeout=10)
        time.sleep(0.6)
        return ActionResult(True, True, "Android BACK sent.")

    if action in {"scroll_down", "scroll_up"}:
        list_scroll = bool(decision.get("list_scroll"))
        x = int(obs.device_width * (0.28 if list_scroll else 0.50))
        if action == "scroll_down":
            start_y = int(obs.device_height * (0.62 if list_scroll else 0.76))
            end_y = int(obs.device_height * (0.30 if list_scroll else 0.30))
        else:
            start_y = int(obs.device_height * (0.30 if list_scroll else 0.30))
            end_y = int(obs.device_height * (0.62 if list_scroll else 0.76))
        duration = "380" if list_scroll else "500"
        logger.info("[SCROLL] %s list=%s native=%s,%s -> %s,%s", action, list_scroll, x, start_y, x, end_y)
        adb(["shell", "input", "swipe", str(x), str(start_y), str(x), str(end_y), duration], timeout=15)
        time.sleep(0.5)
        return ActionResult(True, True, f"{action} executed.")

    if action in {"scroll_left", "scroll_right"}:
        y = obs.device_height // 2
        if action == "scroll_left":
            start_x, end_x = int(obs.device_width * 0.78), int(obs.device_width * 0.22)
        else:
            start_x, end_x = int(obs.device_width * 0.22), int(obs.device_width * 0.78)
        adb([
            "shell", "input", "swipe", str(start_x), str(y), str(end_x), str(y), "500"
        ], timeout=15)
        time.sleep(1.2)
        return ActionResult(True, True, f"{action} executed.")

    if action in {"swipe", "drag"}:
        if not all(isinstance(point, list) and len(point) == 2 for point in (gesture_start, gesture_end)):
            return ActionResult(False, False, f"{action} requires gesture_start and gesture_end.")
        start_x, start_y = normalized_to_native(
            gesture_start, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
        )
        end_x, end_y = normalized_to_native(
            gesture_end, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
        )
        duration = "1400" if action == "drag" else "500"
        dropped = adb([
            "shell", "input", "draganddrop", str(start_x), str(start_y),
            str(end_x), str(end_y), duration,
        ], timeout=20)
        if dropped.returncode != 0:
            adb([
                "shell", "input", "swipe", str(start_x), str(start_y),
                str(end_x), str(end_y), duration,
            ], timeout=20)
        if action == "drag":
            _DRAG_DONE["done"] = True
            logger.info("[DRAG] Recorded drop from (%s,%s) to (%s,%s)", start_x, start_y, end_x, end_y)
        time.sleep(1.4)
        return ActionResult(True, True, f"{action} executed from ({start_x},{start_y}) to ({end_x},{end_y}).")

    if action == "select_then_continue":
        points = decision.get("tap_points") or []
        if isinstance(coords, list) and len(coords) == 2:
            points = [coords] + [p for p in points if p != coords]
        if not points:
            return ActionResult(False, False, "select_then_continue needs tap_points.")
        for milli in points[:4]:
            if not (isinstance(milli, list) and len(milli) == 2):
                continue
            px, py = normalized_to_native(
                milli, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
            )
            webview_click(px, py)
            time.sleep(0.22)
        time.sleep(0.35)
        cont = decision.get("continue_coords") or [500, 778]
        if isinstance(cont, list) and len(cont) == 2 and int(cont[1]) < 930:
            cx, cy = normalized_to_native(
                cont, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
            )
            logger.info("[SELECT ONE] Continue after option tap native=(%s,%s)", cx, cy)
            webview_click(cx, cy)
        time.sleep(0.5)
        return ActionResult(True, True, "select_then_continue executed.")

    if action == "keyevent":
        key = str(payload or decision.get("keyevent") or "").strip()
        if not key:
            return ActionResult(False, False, "Missing keyevent.")
        adb(["shell", "input", "keyevent", key], timeout=10)
        time.sleep(0.8)
        return ActionResult(True, True, f"Keyevent {key} sent.")

    if action == "focus_select_continue":
        keys = [
            "KEYCODE_TAB", "KEYCODE_TAB", "KEYCODE_SPACE",
            "KEYCODE_TAB", "KEYCODE_TAB", "KEYCODE_TAB", "KEYCODE_ENTER",
        ]
        logger.info("[SELECT ONE] Keyboard sequence TAB/SPACE/ENTER for %r", target_text)
        for key in keys:
            adb(["shell", "input", "keyevent", key], timeout=10)
            time.sleep(0.18)
        time.sleep(0.6)
        return ActionResult(True, True, "TAB/SPACE/ENTER sequence sent.")

    if action in {"type_text", "type_comment"}:
        if payload in (None, ""):
            return ActionResult(False, False, f"{action} requires input_payload.")

        target_node = node if node and node.get("editable") else editable_candidate(
            obs.ui_nodes, str(decision.get("question_text") or "")
        )
        coords = coerce_tap_coords(coords, (obs.image_width, obs.image_height)) or coords
        if not target_node:
            # The LLM may have seen the field visually but UIAutomator exposes no
            # editable node. In that case use normalized coordinates only after
            # validating they are present.
            if not (isinstance(coords, list) and len(coords) == 2):
                coords = text_entry_field_coords(obs)
            if not (isinstance(coords, list) and len(coords) == 2):
                return ActionResult(False, False, "No editable UI node or coordinates.")
            x, y = normalized_to_native(coords, (obs.image_width, obs.image_height),
                                        (obs.device_width, obs.device_height))
            logger.info("[TEXT FIELD] Focusing WebView field at native=(%s,%s)", x, y)
            if str(decision.get("kb_key") or "") == "age":
                _AGE_FIELD_MISS["n"] = int(_AGE_FIELD_MISS.get("n") or 0) + 1
                webview_click(x, y)
                time.sleep(0.55)
                if not _AGE_SESSION.get("typed"):
                    adb(["shell", "input", "keyevent", "KEYCODE_MOVE_END"], timeout=10)
                    for _ in range(8):
                        adb(["shell", "input", "keyevent", "KEYCODE_DEL"], timeout=10)
                    type_digits(str(payload))
                    time.sleep(0.35)
                    _AGE_SESSION["typed"] = True
                    logger.info("[AGE] Typed %r at native=(%s,%s)", payload, x, y)
                arrow = decision.get("arrow_coords")
                if not (isinstance(arrow, list) and len(arrow) == 2) and "purple_submit_arrow_milli" in globals():
                    arrow = purple_submit_arrow_milli(obs) or mapped_age_arrow_milli(obs)
                if isinstance(arrow, list) and len(arrow) == 2:
                    ax, ay = normalized_to_native(
                        arrow, (obs.image_width, obs.image_height),
                        (obs.device_width, obs.device_height),
                    )
                    time.sleep(0.2)
                    webview_click(ax, ay)
                    logger.info("[AGE] Arrow after type native=(%s,%s) milli=%s", ax, ay, arrow)
                else:
                    logger.info("[AGE] Typed %r at native=(%s,%s) miss=%s",
                                payload, x, y, _AGE_FIELD_MISS.get("n"))
            else:
                tap_native(x, y)
                time.sleep(0.55)
                tap_native(x, y)
                time.sleep(0.45)
                adb(["shell", "input", "keyevent", "KEYCODE_MOVE_END"], timeout=10)
                clear_n = 96 if (
                    open_text_is_garbage(obs.ocr_text)
                    or "any other" in str(obs.ocr_text or "").lower()
                ) else 24
                for _ in range(clear_n):
                    adb(["shell", "input", "keyevent", "KEYCODE_DEL"], timeout=10)
                adb_input_multiline(str(payload).replace("&", " and ").replace("'", ""))
        else:
            type_into_node(target_node, str(payload))

        # Do not automatically click Next. Verification must happen first.
        if str(decision.get("kb_key") or "") == "captcha_code" and payload:
            _CAPTCHA_TYPED["captcha_code"] = str(payload)
            logger.info("[CAPTCHA] Recorded typed code=%r", payload)
        if str(decision.get("kb_key") or "") == "child_age" and payload:
            _CHILD_AGE_TYPED[semantic_screen_signature(obs)] = str(payload).strip()
            logger.info("[CHILD AGE] Marked typed=%r after execute.", payload)
        if action in {"type_text", "type_comment"} and payload and str(decision.get("kb_key") or "") != "age":
            typed_value = str(payload).strip()
            _OPEN_TEXT_TYPED[question_fingerprint(obs)] = typed_value
            _OPEN_TEXT_TYPED[open_text_screen_key(obs)] = typed_value
            logger.info("[OPEN TEXT] Marked typed for this question.")
        return ActionResult(True, True, "Text entry executed.")

    if action == "stage_file":
        local_path = Path(str(payload or ""))
        android_path = str(decision.get("android_file_path") or "")
        if not local_path.is_file() or not android_path:
            return ActionResult(False, False, "Authorized upload file/path is invalid.")
        result = adb(["push", str(local_path), android_path], timeout=60)
        if result.returncode != 0:
            return ActionResult(False, False, "Could not stage the authorized upload file.")
        return ActionResult(True, True, f"Authorized file staged as {Path(android_path).name}.")

    if action == "set_picker_value" and payload not in (None, ""):
        target_node = node if node and node.get("editable") else editable_candidate(
            obs.ui_nodes, str(decision.get("question_text") or "")
        )
        if target_node:
            type_into_node(target_node, str(payload))
            return ActionResult(True, True, "Picker value typed into editable field.")

    if action == "set_slider":
        target_node = node
        if not target_node and target_text:
            target_node = text_match_node(obs.ui_nodes, target_text)
        if all(isinstance(point, list) and len(point) == 2 for point in (gesture_start, gesture_end)):
            start_x, start_y = normalized_to_native(
                gesture_start, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
            )
            end_x, end_y = normalized_to_native(
                gesture_end, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
            )
            adb(["shell", "input", "swipe", str(start_x), str(start_y), str(end_x), str(end_y), "700"], timeout=20)
        elif target_node and isinstance(control_value, (int, float)):
            x1, y1, x2, y2 = target_node["bounds"]
            fraction = max(0.0, min(100.0, float(control_value))) / 100.0
            margin = max(2, int((x2 - x1) * 0.04))
            x = int(x1 + margin + fraction * max(1, (x2 - x1) - 2 * margin))
            y = int((y1 + y2) / 2)
            tap_native(x, y)
        elif isinstance(coords, list) and len(coords) == 2:
            x, y = normalized_to_native(
                coords, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
            )
            tap_native(x, y)
        else:
            return ActionResult(False, False, "Slider requires bounds/value, coordinates or a gesture.")
        time.sleep(1.0)
        return ActionResult(True, True, "Slider value gesture executed.")

    if action in {
        "click", "select_option", "toggle_checkbox", "select_dropdown",
        "open_dropdown", "select_matrix_cell", "open_date_picker",
        "open_time_picker", "set_picker_value", "pick_file",
        "handle_permission", "long_press",
    }:
        target_node = node
        if action != "select_matrix_cell" and not target_node and target_text:
            target_node = text_match_node(obs.ui_nodes, target_text)

        option_xy = (
            option_tap_xy(obs, target_node, target_text)
            if action in {"select_option", "toggle_checkbox"} and not decision.get("skip_object_grounding")
            else None
        )
        if option_xy and action in {"select_option", "toggle_checkbox"} and not (
            decision.get("coordinate_authoritative") is True
            and isinstance(coords, list) and len(coords) == 2
        ):
            x, y = option_xy
            logger.info("[ROW TAP] native=(%s,%s) text=%r", x, y, target_text)
        elif (
            action in {"select_option", "toggle_checkbox", "click", "open_dropdown", "select_dropdown"}
            and decision.get("coordinate_authoritative") is True
            and isinstance(coords, list) and len(coords) == 2
        ):
            x, y = normalized_to_native(
                coords, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
            )
            logger.info("[AUTH TAP] native=(%s,%s) from coords=%s text=%r", x, y, coords, target_text)
            if decision.get("dismiss_keyboard") and str(decision.get("kb_key") or "") != "age":
                adb(["shell", "input", "keyevent", "KEYCODE_BACK"], timeout=10)
                time.sleep(0.45)
                logger.info("[AGE] Keyboard dismissed before Continue")
            if y <= int(obs.device_height * 0.18) and option_xy:
                x, y = option_xy
        elif action == "select_matrix_cell" and isinstance(coords, list) and len(coords) == 2:
            x, y = normalized_to_native(
                coords, (obs.image_width, obs.image_height), (obs.device_width, obs.device_height)
            )
            logger.info("[MATRIX TAP] native=(%s,%s) from coords=%s", x, y, coords)
            if x < 20 and y < 20:
                return ActionResult(False, False, "Refusing matrix tap at (0,0).")
        elif option_xy:
            x, y = option_xy
        elif target_node:
            x, y = node_center(target_node)
        elif decision.get("coordinate_authoritative") is True and isinstance(coords, list) and len(coords) == 2:
            x, y = normalized_to_native(coords, (obs.image_width, obs.image_height),
                                        (obs.device_width, obs.device_height))
        elif target_text and obs.screenshot:
            ocr_target = ocr_text_center(Path(obs.screenshot), target_text)
            if ocr_target:
                ox, oy = ocr_target
                if oy >= int(obs.image_height * 0.88) or oy <= int(obs.image_height * 0.20):
                    logger.warning("[OCR GROUNDING] Ignoring chrome hit (%s,%s) for %r", ox, oy, target_text)
                    ocr_target = None
                else:
                    x, y = ox, oy
                    logger.info("[OCR GROUNDING] Located %r at (%s,%s)", target_text, x, y)
            if not ocr_target and isinstance(coords, list) and len(coords) == 2:
                x, y = normalized_to_native(coords, (obs.image_width, obs.image_height),
                                            (obs.device_width, obs.device_height))
                logger.info("[OCR GROUNDING] Fallback coords=%s native=(%s,%s)", coords, x, y)
            elif not ocr_target:
                return ActionResult(False, False, "No safe target grounding available.")
        elif isinstance(coords, list) and len(coords) == 2:
            x, y = normalized_to_native(coords, (obs.image_width, obs.image_height),
                                        (obs.device_width, obs.device_height))
        else:
            return ActionResult(False, False, "No safe target grounding available.")

        if action == "long_press":
            adb(["shell", "input", "swipe", str(x), str(y), str(x), str(y), "900"], timeout=15)
        elif action in {"open_dropdown", "select_dropdown"}:
            logger.info("[DROPDOWN TAP] native=(%s,%s) text=%r", x, y, target_text)
            adb(["shell", "input", "swipe", str(x), str(y), str(x), str(y), "140"], timeout=15)
            time.sleep(0.35)
        else:
            height = max(int(obs.device_height or 0), int(obs.image_height or 0), 1)
            tlow = str(target_text or "").lower()
            milli_y = 0
            tc = decision.get("target_coords")
            if isinstance(tc, (list, tuple)) and len(tc) >= 2:
                try:
                    milli_y = int(tc[1])
                except (TypeError, ValueError):
                    milli_y = 0
            nav_milli = safe_navigation_top_milli(obs) if "safe_navigation_top_milli" in globals() else 945
            nav_y = int(height * nav_milli / 1000)
            if y >= nav_y:
                logger.warning(
                    "[SAFE TAP] Refusing system-nav tap native=(%s,%s) nav_top=%s text=%r",
                    x, y, nav_milli, target_text,
                )
                return ActionResult(False, False, "Refusing system-nav tap.")
            if decision.get("object_map_grounded"):
                logger.info(
                    "[SAFE TAP] Object-mapped target bounds=%s native=(%s,%s) nav_top=%s",
                    decision.get("target_bounds"), x, y, nav_milli,
                )
            if action == "select_option" or "start" in tlow or "agree" in tlow or "participate" in tlow or decision.get("i_agree_continue") or (
                str(decision.get("kb_key") or "") == "age" and "continue" in tlow
            ):
                webview_click(x, y)
                if decision.get("i_agree_continue"):
                    tap_native(x, y)
            else:
                tap_native(x, y)
        if decision.get("i_agree_pick"):
            _I_AGREE_SESSION["tapped"] = True
            logger.info("[I AGREE] Marked tapped after execute.")

        if action == "select_option" and str(decision.get("kb_key") or "") == "number_of_children":
            _CHILDREN_TAPPED[semantic_screen_signature(obs)] = str(
                target_text or decision.get("input_payload") or ""
            ).strip()
            logger.info("[CHILDREN] Marked tapped=%r after execute.", _CHILDREN_TAPPED.get(semantic_screen_signature(obs)))
        if action == "select_option" and decision.get("select_all_pick"):
            if not select_all_is_brand_bought(obs.ocr_text):
                pick = str(decision.get("select_all_pick") or "")
                done = list(_SELECT_ALL_SESSION.get("done") or [])
                if pick and pick not in done:
                    done.append(pick)
                    _SELECT_ALL_SESSION["done"] = done
                    logger.info("[SELECT ALL] Marked done=%s", done)
        if action == "select_matrix_cell" and decision.get("maxdiff_side"):
            side = str(decision.get("maxdiff_side") or "")
            row = str(decision.get("maxdiff_row") or "")
            if side in {"most", "least"} and row:
                _MAXDIFF_SESSION[side] = row
                logger.info("[MAXDIFF] Marked %s=%r", side, row)
        if action == "select_option" and decision.get("carousel_item"):
            _CAROUSEL_SESSION["item"] = str(decision.get("carousel_item"))
            _CAROUSEL_SESSION["answered"] = True
            _CAROUSEL_SESSION["right_stagnant"] = 0
            logger.info("[CAROUSEL] Marked %r answered.", _CAROUSEL_SESSION["item"])
        if action == "click" and decision.get("carousel_advance"):
            prev = str(decision.get("carousel_item") or _CAROUSEL_SESSION.get("item") or "")
            if prev:
                done = list(_CAROUSEL_SESSION.get("done") or [])
                if prev.lower() not in {x.lower() for x in done}:
                    done.append(prev)
                _CAROUSEL_SESSION["done"] = done
            _CAROUSEL_SESSION["answered"] = False
            _CAROUSEL_SESSION["item"] = ""
            logger.info("[CAROUSEL] Advanced after %r done=%s", prev, _CAROUSEL_SESSION["done"])
        if action == "click" and decision.get("carousel_review"):
            _CAROUSEL_SESSION["left_reviews"] = int(_CAROUSEL_SESSION.get("left_reviews") or 0) + 1
            _CAROUSEL_SESSION["answered"] = False
            if _CAROUSEL_SESSION["left_reviews"] >= 8:
                _CAROUSEL_SESSION["review_done"] = True
            logger.info("[CAROUSEL] Reviewed left %s", _CAROUSEL_SESSION["left_reviews"])

        time.sleep(1.0)
        return ActionResult(True, True, f"{action} executed at ({x},{y}).")

    if action == "request_human":
        logger.warning("[HUMAN] %s", decision.get("visual_reasoning", "LLM requested help."))
        return ActionResult(False, False, "Human intervention requested.")

    return ActionResult(False, False, f"Unsupported action: {action}")


# ------------------------------------------------------------------------------
# Postcondition verification / recovery
# ------------------------------------------------------------------------------

def screen_changed(before: Observation, after_path: Path) -> bool:
    return perceptual_hash(before.screenshot) != perceptual_hash(after_path) if before.screenshot else True


def verify_postcondition(
    decision: dict[str, Any],
    before: Observation,
    after: Observation,
) -> bool:
    condition = str(decision.get("postcondition") or "").lower()

    introduced_error = required_validation_visible(after) and not required_validation_visible(before)
    if introduced_error and ("screen changed" in condition or required_is_progression(decision)):
        logger.warning("[VERIFY] Action introduced a validation error; screen change is failure.")
        return False

    if decision.get("required_gate_progression"):
        return required_progression_verified(before, after)

    if "cookie overlay dismissed" in condition:
        return not cookie_consent_visible(after.ocr_text, after.ui_nodes)

    if "permission dialog dismissed" in condition:
        return not permission_dialog_visible(after.ocr_text, after.ui_nodes)

    if "document picker dismissed" in condition:
        return not document_picker_visible(after.ocr_text, after.ui_nodes)

    if "authorized file staged" in condition:
        return android_file_exists(str(decision.get("android_file_path") or ""))

    if "maxdiff most selected" in condition or "maxdiff least selected" in condition:
        side = "most" if "most" in condition else "least"
        row = str(decision.get("maxdiff_row") or "")
        if row and str(_MAXDIFF_SESSION.get(side) or "").lower() == row.lower():
            logger.info("[VERIFY] MaxDiff %s=%s issued.", side, row)
            return True
        rows = maxdiff_row_centers(after)
        vis_most, vis_least = maxdiff_filled(after, rows)
        got = vis_most if side == "most" else vis_least
        ok = bool(got)
        logger.info("[VERIFY] MaxDiff %s visual=%r wanted=%r ok=%s", side, got, row, ok)
        return ok

    if "screen changed" in condition:
        raw_target = str(decision.get("target_text") or "")
        option_target = normalized_option_label(raw_target)
        option_click = bool(
            re.search(r"\b(?:radio|option|choice)\b", raw_target.lower())
            or decision.get("irish_region_radio")
        )
        if option_click and option_target:
            ok = selected_option_visual(after, option_target)
            logger.info("[VERIFY] Exact option click target=%r selected=%s", option_target, ok)
            return ok
        if decision.get("maxdiff_done") and before.screen_hash == after.screen_hash:
            _MAXDIFF_SESSION["force_scroll"] = True
            logger.warning("[VERIFY] MaxDiff Continue miss; next cycle scrolls instead of retapping the nav bar.")
        if decision.get("six_step_footer") and active_question_signature(before) == active_question_signature(after):
            logger.warning("[SIX] 5 same question after footer; a hash change is not progress.")
            return False
        return before.screen_hash != after.screen_hash

    if "contains" in condition and decision.get("input_payload"):
        expected = re.sub(r"\s+", " ", str(decision["input_payload"]).lower()).strip()
        visible = re.sub(r"\s+", " ", after.ocr_text.lower()).strip()
        node_values = [
            re.sub(r"\s+", " ", node_text(node).lower()).strip()
            for node in after.ui_nodes
        ]
        snippets = [expected]
        if len(expected) > 48:
            snippets.append(expected[:48].rstrip())
        return any(
            snippet and (snippet in visible or any(snippet in value for value in node_values))
            for snippet in snippets
        )

    if "dropdown is open" in condition:
        opened = county_dropdown_open(after.ocr_text)
        if not opened:
            logger.warning("[VERIFY] County list is still closed (need 4+ county names).")
        return opened

    if "selected option" in condition:
        wanted_exact = str(decision.get("target_text") or decision.get("input_payload") or "").strip()
        if str(decision.get("kb_key") or "") == "gender" or (
            gender_choice_screen(before) and str(decision.get("action") or "") == "select_option"
        ):
            if "next" in wanted_exact.lower() or wanted_exact.lower() in {"female", "other"}:
                logger.warning("[VERIFY] Refusing %r as the stored gender.", wanted_exact)
                return False
            if not selected_option_visual(after, wanted_exact or "Male"):
                logger.warning("[VERIFY] %r is not the checked gender row.", wanted_exact)
                return False
            logger.info("[VERIFY] Gender row %r is selected.", wanted_exact)
            return True
        if decision.get("irish_region_radio") or irish_region_radio_question_visible(before.ocr_text):
            wanted = str(decision.get("target_text") or "").strip()
            structured = any(
                (node.get("checked") or node.get("selected"))
                and normalized_option_label(wanted) == normalized_option_label(node_text(node))
                for node in after.ui_nodes
            )
            visual = selected_option_visual(after, wanted)
            if structured or visual:
                _IRISH_REGION_SESSION.update({"key": required_question_key(after), "verified": True})
                logger.info("[VERIFY] Irish region %r selected on the same question.", wanted)
                return True
            logger.warning("[VERIFY] Irish region row did not show a selected-state change.")
            return False
        if county_question_visible(after.ocr_text) or county_question_visible(before.ocr_text):
            wanted = str(decision.get("target_text") or decision.get("input_payload") or "").strip()
            if wanted.lower() == intended_county(after).lower():
                if county_dropdown_open(after.ocr_text):
                    if county_picked_visual(after) or _COUNTY_SESSION.get("tapped"):
                        _COUNTY_SESSION["picked"] = True
                        logger.info("[VERIFY] %s selected; list stays open until Continue.", wanted)
                        return True
                    logger.warning("[VERIFY] County list still open after tapping %s.", wanted)
                    return False
                shown = county_displayed_value(after)
                ok = bool(shown and shown.lower() == wanted.lower())
                if not ok and wanted.lower() in (after.ocr_text or "").lower():
                    ok = not county_dropdown_open(after.ocr_text)
                if not ok:
                    logger.warning("[VERIFY] County field shows %r, wanted %r.", shown, wanted)
                return ok
        if children_count_question_visible(after.ocr_text) or children_count_question_visible(before.ocr_text):
            wanted = str(decision.get("target_text") or decision.get("input_payload") or "").strip()
            if children_pick_complete(after, wanted) or children_pick_complete(before, wanted):
                logger.info("[VERIFY] Children %s issued; leftover red banner is not a failed select.", wanted)
                return True
        if carousel_row_question_visible(after.ocr_text) or carousel_row_question_visible(before.ocr_text):
            if carousel_has_green_selection(after):
                logger.info("[VERIFY] Carousel row is green; leftover red banner is expected until all rows are done.")
                return True
            logger.warning("[VERIFY] Carousel option is not green yet; will retarget a lower tile.")
            _CAROUSEL_SESSION["tap_try"] = int(_CAROUSEL_SESSION.get("tap_try") or 0) + 1
            return False
        if decision.get("select_all_pick") or str(decision.get("kb_key") or "") in {"bread_brands_bought", "bread_claims"}:
            if select_all_lime_band_count(after) >= 1:
                logger.info("[VERIFY] Select-all lime checkbox is visible; red banner waits until Continue.")
                return True
        if looks_like_single_choice(after.ocr_text) or looks_like_single_choice(before.ocr_text) or str(decision.get("kb_key") or "") == "hovis_unavailable_action":
            changed = before.screen_hash != after.screen_hash
            if changed or select_all_lime_band_count(after) >= 1:
                _SELECT_ONE_SESSION["verified"] = True
                _SELECT_ONE_SESSION["misses"] = 0
                logger.info("[VERIFY] Select-one tap landed; red banner waits for Continue.")
                return True
            _SELECT_ONE_SESSION["misses"] = int(_SELECT_ONE_SESSION.get("misses") or 0) + 1
            logger.warning("[VERIFY] Select-one tap missed (hash unchanged); will retarget miss=%s.",
                           _SELECT_ONE_SESSION["misses"])
            return False
        if comfort_scale_visible(after.ocr_text) or comfort_scale_visible(before.ocr_text):
            logger.info("[VERIFY] Comfort Likert tick; required banner stays until Continue.")
            return True
        if select_up_to_n_visible(after.ocr_text) or select_up_to_n_visible(before.ocr_text):
            logger.info("[VERIFY] Select-up-to-N tick; required banner stays until 3 boxes are checked.")
            return True
        if survey_validation_error(after) and not children_count_question_visible(after.ocr_text):
            logger.warning("[VERIFY] Selection did not clear the red error banner.")
            return False
        target = str(decision.get("target_text") or "").strip().lower()
        structured = False
        for node in after.ui_nodes:
            if not (node.get("checked") or node.get("selected")):
                continue
            label = node_text(node).strip().lower()
            if not target or target in label or label in target:
                structured = True
                break
        progress_hit = False
        if target:
            signature = semantic_screen_signature(before)
            progress_hit = any(
                target == str(label).strip().lower()
                or target in option_match_keys(str(label))
                for label in _MULTI_SELECT_PROGRESS.get(signature, [])
            )
        visual = selected_answer_visual_signal(after)
        changed = before.screen_hash != after.screen_hash
        if structured or visual or changed or progress_hit:
            return True
        return False

    if "matrix cell selected" in condition:
        logger.info("[VERIFY] Accepting matrix cell tap without hash/checked evidence.")
        return True

    if any(term in condition for term in ("slider", "drag", "reordered", "swiped")):
        return before.screen_hash != after.screen_hash

    if "completion" in condition:
        text = after.ocr_text.lower()
        return any(x in text for x in ("complete", "completed", "thank you", "finished", "submitted"))

    # Conservative default: action caused a state change.
    return before.screen_hash != after.screen_hash
