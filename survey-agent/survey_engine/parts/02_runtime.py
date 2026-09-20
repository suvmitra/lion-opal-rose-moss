# 02_runtime.py — shared engine namespace (do not import directly)

@dataclass
class Observation:
    step: int
    screenshot: Optional[str]
    image_width: int
    image_height: int
    device_width: int
    device_height: int
    screen_hash: Optional[str]
    ocr_text: str
    ui_nodes: list[dict[str, Any]]
    kb: dict[str, Any]
    persona: dict[str, Any]
    screen_phase: str
    survey_tiles: list[dict[str, Any]]


@dataclass
class ActionResult:
    success: bool
    changed: bool
    message: str
    after_hash: Optional[str] = None


def write_state(state: dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ------------------------------------------------------------------------------
# Logging / fresh run
# ------------------------------------------------------------------------------

def initialize_fresh_run() -> bool:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    for child in SCREENSHOT_DIR.iterdir():
        try:
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
        except Exception as exc:
            print(f"Warning: could not remove {child}: {exc}")

    cleanup_ok = True
    for path in (DEBUG_LOG_FILE, ACTION_LOG_FILE):
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_text("", encoding="utf-8")
        except Exception as exc:
            cleanup_ok = False
            print(f"Warning: could not clear {path}: {exc}")

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_state({
            "version": VERSION,
            "status": "initializing_fresh_run",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "steps": 0,
            "completed": False,
            "last_screen_hash": None,
        })
    except Exception as exc:
        cleanup_ok = False
        print(f"Warning: could not reset {STATE_FILE}: {exc}")

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    fh = logging.FileHandler(DEBUG_LOG_FILE, mode="w", encoding="utf-8")
    sh = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d - %(message)s")
    fh.setFormatter(fmt)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)

    reset_matrix_session()
    _CAROUSEL_SESSION.update({"item": "", "answered": False, "done": [], "right_stagnant": 0, "tap_try": 0, "left_reviews": 0, "review_done": False})
    _MAXDIFF_SESSION.update({"key": "", "most": "", "least": "", "scrolls": 0, "force_scroll": False})
    _SELECT_ALL_SESSION.update({"key": "", "done": [], "planned": [], "scrolls": 0})
    _SELECT_ONE_SESSION.update({"key": "", "taps": 0, "misses": 0, "verified": False})
    _I_AGREE_SESSION.update({"tapped": False})
    _VISUAL_RADIO_CACHE.clear()
    _OCR_LINE_CACHE.clear()
    _OPEN_TEXT_TYPED.clear()
    _OPEN_TEXT_DONE.clear()
    global _DEVICE_SIZE_CACHE, _FOREGROUND_OK_UNTIL, _SALAD_ONLINE
    _DEVICE_SIZE_CACHE = None
    _FOREGROUND_OK_UNTIL = 0.0
    _SALAD_ONLINE = True
    logger.info("=" * 78)
    logger.info("FRESH SURVEY AUTOMATION SESSION - v%s", VERSION)
    logger.info(
        "Fresh-run cleanup=%s: screenshots, temporary vision files, debug log, "
        "action log and agent state reset; persistent KB retained.",
        "passed" if cleanup_ok else "incomplete",
    )
    logger.info("=" * 78)
    if not cleanup_ok:
        logger.error("Fresh-run cleanup failed; refusing to continue with stale artifacts.")
    return cleanup_ok


def log_action(row: dict[str, Any]) -> None:
    exists = ACTION_LOG_FILE.exists() and ACTION_LOG_FILE.stat().st_size > 0
    fields = [
        "timestamp", "step", "action", "target", "payload",
        "decision_source", "confidence", "learned_action_confidence",
        "screen_phase", "post_action_phase", "postcondition", "verified",
        "success", "changed", "message"
    ]
    with ACTION_LOG_FILE.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fields})


# ------------------------------------------------------------------------------
# ADB/device
# ------------------------------------------------------------------------------

def adb(args: list[str], timeout: int = 30, check: bool = False) -> subprocess.CompletedProcess:
    cmd = [ADB_PATH]
    if DEVICE_ID:
        cmd += ["-s", DEVICE_ID]
    cmd += args

    last_exc: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            result = subprocess.run(
                cmd, capture_output=True, timeout=timeout,
                text=False
            )
            if check and result.returncode != 0:
                raise RuntimeError(
                    f"ADB failed ({result.returncode}): "
                    f"{result.stderr.decode(errors='replace')[:500]}"
                )
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning("ADB attempt %s failed: %s", attempt, exc)
            time.sleep(0.5)
    raise RuntimeError(f"ADB command failed after retries: {last_exc}")


def adb_text(args: list[str], timeout: int = 30) -> str:
    result = adb(args, timeout=timeout)
    return (result.stdout or b"").decode("utf-8", errors="replace")


def discover_device() -> bool:
    """Discover an online Android device using a host-level ADB command.

    Important: discovery must NOT use adb(), because adb() adds ``-s DEVICE_ID``
    to device-scoped commands. ``adb devices -l`` is a host/server command and
    must run before a transport is selected.
    """
    global DEVICE_ID

    if not Path(ADB_PATH).exists():
        logger.error("ADB executable not found: %s", ADB_PATH)
        return False

    try:
        result = subprocess.run(
            [ADB_PATH, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        logger.error("ADB device discovery failed to execute: %s", exc)
        return False

    output = result.stdout or ""
    stderr = result.stderr or ""

    if result.returncode != 0:
        logger.error(
            "ADB device discovery returned code %s. stdout=%r stderr=%r",
            result.returncode, output, stderr
        )
        return False

    online_devices = []
    non_online = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices attached"):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        serial, state = parts[0], parts[1]
        if state == "device":
            online_devices.append(serial)
        else:
            non_online.append((serial, state))

    if not online_devices:
        logger.error(
            "No online ADB device found. Raw `adb devices -l` output: %r%s",
            output,
            f" | non-online states={non_online}" if non_online else "",
        )
        return False

    if DEVICE_ID:
        if DEVICE_ID not in online_devices:
            logger.error(
                "Configured DEVICE_ID '%s' is not online. Online devices: %s. Raw output: %r",
                DEVICE_ID, online_devices, output
            )
            return False
    else:
        if len(online_devices) > 1:
            logger.error(
                "Multiple online ADB devices found: %s. Set DEVICE_ID in .env to choose one.",
                online_devices
            )
            return False
        DEVICE_ID = online_devices[0]

    logger.info("ADB device online and selected: %s", DEVICE_ID)
    return True


_OCR_LINE_CACHE: dict[tuple[str, int, float], list[dict[str, Any]]] = {}
_DEVICE_SIZE_CACHE: Optional[tuple[int, int]] = None
_FOREGROUND_OK_UNTIL = 0.0


def get_device_size() -> tuple[int, int]:
    global _DEVICE_SIZE_CACHE
    if _DEVICE_SIZE_CACHE and _DEVICE_SIZE_CACHE[0] > 0:
        return _DEVICE_SIZE_CACHE
    text = adb_text(["shell", "wm", "size"], timeout=10)
    # Prefer Physical size; otherwise Override size; otherwise screenshot size.
    matches = re.findall(r"(?:Physical size|Override size):\s*(\d+)x(\d+)", text)
    if matches:
        # Last match is normally the effective override.
        w, h = map(int, matches[-1])
        _DEVICE_SIZE_CACHE = (w, h)
        return w, h
    logger.warning("Could not determine display size from wm size: %r", text)
    return 0, 0


def get_foreground_window() -> str:
    checks = [
        (["shell", "dumpsys", "activity", "activities"],
         ("topResumedActivity", "mResumedActivity", "ResumedActivity")),
        (["shell", "dumpsys", "window", "windows"],
         ("mCurrentFocus", "mFocusedApp", "mFocusedWindow")),
        (["shell", "dumpsys", "window", "displays"],
         ("mCurrentFocus", "mFocusedApp", "mFocusedWindow")),
    ]
    for command, keys in checks:
        try:
            text = adb_text(command, timeout=15)
        except Exception:
            continue
        for key in keys:
            for line in text.splitlines():
                if key in line:
                    return line.strip()
    return "UNKNOWN"


def in_system_nav(bounds: list[Any], height: int) -> bool:
    if not isinstance(bounds, list) or len(bounds) != 4 or height <= 0:
        return False
    return int(bounds[1]) >= int(height * 0.88)


def in_header_chrome(bounds: list[Any], height: int) -> bool:
    if not isinstance(bounds, list) or len(bounds) != 4 or height <= 0:
        return False
    y1, y2 = int(bounds[1]), int(bounds[3])
    return y2 <= int(height * 0.16) or (y1 + y2) / 2 < height * 0.18


def option_node_for_text(obs: Observation, target: str) -> Optional[dict[str, Any]]:
    """Match an option label to a content-area node, never the Android nav bar."""
    wanted = normalize_choice(target)
    if not wanted:
        return None
    candidates: list[dict[str, Any]] = []
    for node in obs.ui_nodes:
        bounds = node.get("bounds") or []
        if in_system_nav(bounds, obs.image_height):
            continue
        if len(bounds) == 4 and bounds[3] <= obs.image_height * 0.10:
            continue
        label = node_text(node)
        if not label:
            continue
        got = normalize_choice(label)
        if wanted == got or wanted in got or (len(got) >= 12 and got in wanted):
            candidates.append(node)
    if candidates:
        return max(
            candidates,
            key=lambda node: (
                len(node_text(node)),
                1 if node.get("clickable") or node.get("checkable") else 0,
            ),
        )
    safe = [
        node for node in obs.ui_nodes
        if not in_system_nav(node.get("bounds") or [], obs.image_height)
    ]
    return text_match_node(safe, target)


def ensure_survey_foreground() -> None:
    """Keep the TopSurveys activity resumed; a nav-bar tap can send it home."""
    global _FOREGROUND_OK_UNTIL
    if time.time() < _FOREGROUND_OK_UNTIL:
        return
    foreground = get_foreground_window()
    lowered = foreground.lower()
    if any(token in lowered for token in (
        SURVEY_PACKAGE.lower(),
        "com.android.chrome",
        "org.chromium",
        "webview",
        "customtabs",
    )):
        _FOREGROUND_OK_UNTIL = time.time() + 10.0
        return
    logger.warning("[FOREGROUND] Survey is not resumed (%s); relaunching %s", foreground, SURVEY_ACTIVITY)
    try:
        adb(
            ["shell", "am", "start", "--activity-single-top", "-n", SURVEY_ACTIVITY],
            timeout=15,
        )
        time.sleep(0.8)
        _FOREGROUND_OK_UNTIL = time.time() + 4.0
    except Exception as exc:
        logger.warning("[FOREGROUND] Relaunch failed: %s", exc)


def valid_salad_organization(value: str) -> bool:
    """Return True only for a real-looking Salad organization slug."""
    value = (value or "").strip()
    placeholder_markers = ("your_", "your-", "placeholder", "example", "organization_slug")
    if any(marker in value.lower() for marker in placeholder_markers):
        return False
    return bool(re.fullmatch(r"[a-z][a-z0-9-]{0,61}[a-z0-9]", value))


# ------------------------------------------------------------------------------
# Screenshot + OCR + UIAutomator
# ------------------------------------------------------------------------------

def screenshot_bytes() -> bytes:
    result = adb(["exec-out", "screencap", "-p"], timeout=30)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(
            "screencap failed: " +
            (result.stderr or b"").decode(errors="replace")[:500]
        )
    return result.stdout


def capture_screenshot(
    step: int,
    save: bool = True,
    previous_hash: Optional[str] = None,
    previous_path: Optional[str] = None,
) -> tuple[Path, tuple[int, int], str, str, bool]:
    raw = screenshot_bytes()
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    phash = str(imagehash.phash(image))
    saved = save

    if (
        save
        and previous_hash
        and phash == previous_hash
        and previous_path
        and Path(previous_path).exists()
    ):
        path = Path(previous_path)
        saved = False
        logger.info(
            "[SCREENSHOT DEDUP] phash=%s unchanged; reusing %s",
            phash, path
        )
    elif save:
        path = SCREENSHOT_DIR / f"step_{step:04d}.png"
        image.save(path, format="PNG")
    else:
        path = SCREENSHOT_DIR / f"_verify_{step}_{int(time.time()*1000)}.png"
        image.save(path, format="PNG")

    sha = hashlib.sha256(raw).hexdigest()
    logger.info(
        "[SCREENSHOT] %s | size=%sx%s | sha256=%s | phash=%s | saved=%s",
        path, *image.size, sha[:16], phash, saved
    )
    return path, image.size, sha, phash, saved


def perceptual_hash(path: Path) -> str:
    with Image.open(path) as img:
        return str(imagehash.phash(img))


def ocr(path: Path) -> str:
    try:
        img = cv2.imread(str(path))
        if img is None:
            return ""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=1.25, fy=1.25, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return pytesseract.image_to_string(
            Image.fromarray(enhanced),
            config="--oem 3 --psm 6"
        ).strip()
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""


def parse_bounds(bounds: str) -> Optional[list[int]]:
    nums = [int(x) for x in re.findall(r"\d+", bounds or "")]
    return nums if len(nums) == 4 else None


def dump_ui_nodes() -> list[dict[str, Any]]:
    remote = "/sdcard/survey_window.xml"
    result = adb(["shell", "uiautomator", "dump", "--compressed", remote], timeout=20)
    if result.returncode != 0:
        logger.warning("UIAutomator dump failed.")
        return []

    xml = adb_text(["exec-out", "cat", remote], timeout=15)
    if not xml.strip():
        return []

    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml)
    except Exception as exc:
        logger.warning("UI XML parse failed: %s", exc)
        return []

    nodes: list[dict[str, Any]] = []
    for idx, node in enumerate(root.iter()):
        bounds = parse_bounds(node.attrib.get("bounds", ""))
        if not bounds:
            continue

        text = (node.attrib.get("text") or "").strip()
        desc = (node.attrib.get("content-desc") or "").strip()
        cls = (node.attrib.get("class") or "").split(".")[-1]

        nodes.append({
            "id": idx,
            "text": text,
            "content_desc": desc,
            "class": cls,
            "package": node.attrib.get("package", ""),
            "resource_id": node.attrib.get("resource-id", ""),
            "clickable": node.attrib.get("clickable") == "true",
            "checkable": node.attrib.get("checkable") == "true",
            "checked": node.attrib.get("checked") == "true",
            "editable": node.attrib.get("editable") == "true",
            "enabled": node.attrib.get("enabled") != "false",
            "focusable": node.attrib.get("focusable") == "true",
            "selected": node.attrib.get("selected") == "true",
            "bounds": bounds,
        })

    logger.info("[UI] %d nodes captured; editable=%d clickable=%d",
                len(nodes),
                sum(1 for n in nodes if n["editable"]),
                sum(1 for n in nodes if n["clickable"]))
    return nodes
