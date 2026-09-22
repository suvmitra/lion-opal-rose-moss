# 05_kb_match.py — shared engine namespace (do not import directly)



def ocr_line_nodes(path: Path, psm: int = 6) -> list[dict[str, Any]]:
    """Return OCR lines with native screenshot bounds for grounding/parsing."""
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        mtime = 0.0
    cache_key = (str(path), int(psm), float(mtime))
    cached = _OCR_LINE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        with Image.open(path) as image:
            data = pytesseract.image_to_data(
                image.convert("RGB"),
                output_type=pytesseract.Output.DICT,
                config=f"--oem 3 --psm {int(psm)}",
            )
    except Exception as exc:
        logger.warning("OCR coordinate extraction failed: %s", exc)
        return []

    grouped: dict[tuple[int, int, int], list[tuple[str, int, int, int, int]]] = {}
    for index, raw_text in enumerate(data.get("text", [])):
        text = str(raw_text or "").strip()
        if not text:
            continue
        try:
            confidence = float(data.get("conf", [0])[index])
        except (TypeError, ValueError, IndexError):
            confidence = 0
        if confidence < 20:
            continue
        key = (
            int(data.get("block_num", [0])[index]),
            int(data.get("par_num", [0])[index]),
            int(data.get("line_num", [0])[index]),
        )
        x = int(data["left"][index])
        y = int(data["top"][index])
        width = int(data["width"][index])
        height = int(data["height"][index])
        grouped.setdefault(key, []).append((text, x, y, x + width, y + height))

    result: list[dict[str, Any]] = []
    for words in grouped.values():
        words.sort(key=lambda item: item[1])
        segments: list[list[tuple[str, int, int, int, int]]] = []
        for word in words:
            if not segments or word[1] - segments[-1][-1][3] > 100:
                segments.append([word])
            else:
                segments[-1].append(word)
        for segment in segments:
            line_id = len(result)
            result.append({
                "id": f"ocr-{line_id}",
                "text": " ".join(item[0] for item in segment),
                "content_desc": "",
                "class": "OCRLine",
                "resource_id": "",
                "clickable": False,
                "checkable": False,
                "checked": False,
                "editable": False,
                "enabled": True,
                "focusable": False,
                "selected": False,
                "bounds": [
                    min(item[1] for item in segment),
                    min(item[2] for item in segment),
                    max(item[3] for item in segment),
                    max(item[4] for item in segment),
                ],
            })
    if len(_OCR_LINE_CACHE) >= 16:
        _OCR_LINE_CACHE.pop(next(iter(_OCR_LINE_CACHE)))
    _OCR_LINE_CACHE[cache_key] = result
    return result


def extract_survey_tiles(
    nodes: list[dict[str, Any]], image_width: int, image_height: int
) -> list[dict[str, Any]]:
    """Group duration/payout/rating text into tappable Featured Survey cards."""
    duration_re = re.compile(r"\b(\d{1,3})\s*min\b", re.I)
    payout_re = re.compile(r"[€$£]\s*(\d+(?:[.,]\d+)?)", re.I)
    rating_re = re.compile(r"\b([1-5](?:\.\d+)?)\s*\(\s*(\d+)\s*\)")

    header_bottom = int(image_height * 0.28)
    header_markers = (
        "featured survey", "best match", "short surveys", "highest payout",
    )
    for node in nodes:
        if (
            any(marker in node_text(node).lower() for marker in header_markers)
            and node.get("bounds")
        ):
            header_bottom = max(header_bottom, int(node["bounds"][3]))

    atoms: list[dict[str, Any]] = []
    screen_area = image_width * image_height
    for node in nodes:
        text = node_text(node)
        bounds = node.get("bounds")
        if not text or not isinstance(bounds, list) or len(bounds) != 4:
            continue
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        if width <= 0 or height <= 0 or width * height > screen_area * 0.25:
            continue
        center_x = (bounds[0] + bounds[2]) // 2
        center_y = (bounds[1] + bounds[3]) // 2
        if center_y <= header_bottom or center_y >= image_height * 0.92:
            continue
        duration = duration_re.search(text)
        payout = payout_re.search(text)
        rating = rating_re.search(text)
        if not (duration or payout or rating):
            continue
        atoms.append({
            "text": text,
            "bounds": list(map(int, bounds)),
            "cx": center_x,
            "cy": center_y,
            "duration": int(duration.group(1)) if duration else None,
            "payout": float(payout.group(1).replace(",", ".")) if payout else None,
            "rating": float(rating.group(1)) if rating else None,
        })

    clusters: list[dict[str, Any]] = []
    x_tolerance = image_width * 0.28
    y_tolerance = image_height * 0.10
    for atom in sorted(atoms, key=lambda item: (item["cy"], item["cx"])):
        target = next((
            cluster for cluster in clusters
            if abs(atom["cx"] - cluster["cx"]) <= x_tolerance
            and abs(atom["cy"] - cluster["cy"]) <= y_tolerance
        ), None)
        if target is None:
            target = {
                "items": [], "cx": atom["cx"], "cy": atom["cy"],
                "bounds": list(atom["bounds"]), "duration": None,
                "payout": None, "rating": None,
            }
            clusters.append(target)
        target["items"].append(atom)
        target["bounds"] = [
            min(target["bounds"][0], atom["bounds"][0]),
            min(target["bounds"][1], atom["bounds"][1]),
            max(target["bounds"][2], atom["bounds"][2]),
            max(target["bounds"][3], atom["bounds"][3]),
        ]
        target["cx"] = int(sum(item["cx"] for item in target["items"]) / len(target["items"]))
        target["cy"] = int(sum(item["cy"] for item in target["items"]) / len(target["items"]))
        for field in ("duration", "payout", "rating"):
            if atom[field] is not None:
                target[field] = atom[field]

    tiles: list[dict[str, Any]] = []
    for cluster in clusters:
        if cluster["duration"] is None and cluster["payout"] is None:
            continue
        bounds = cluster["bounds"]
        # The text cluster lies inside the card; its mean center is a safe tap.
        center = [cluster["cx"], cluster["cy"]]
        tiles.append({
            "tile_id": len(tiles) + 1,
            "duration_minutes": cluster["duration"],
            "payout": cluster["payout"],
            "rating": cluster["rating"],
            "bounds": bounds,
            "center": center,
            "label": (
                f"Featured Survey {cluster['duration'] or '?'} min "
                f"{cluster['payout'] if cluster['payout'] is not None else '?'}"
            ),
        })

    tiles.sort(key=lambda tile: (tile["center"][1], tile["center"][0]))
    for index, tile in enumerate(tiles, 1):
        tile["tile_id"] = index
    logger.info("[TILE PARSER] Discovered %s featured survey tiles: %s", len(tiles), tiles)
    return tiles


# ------------------------------------------------------------------------------
# Knowledge base
# ------------------------------------------------------------------------------

CANONICAL_ALIASES = {
    "postcode": "postal_code",
    "post_code": "postal_code",
    "zip": "postal_code",
    "zip_code": "postal_code",
    "town": "city",
    "employment": "employment_status",
    "job_status": "employment_status",
    "children": "has_children",
    "smoke": "smoking_status",
    "language": "preferred_language",
    "pets": "household_pets",
    "household_pet": "household_pets",
    "birthdate": "date_of_birth",
    "birth_date": "date_of_birth",
    "dob": "date_of_birth",
}



# ------------------------------------------------------------------------------
# Human answer matching (vendored). Sibling file is optional.
# ------------------------------------------------------------------------------

OPTION_CHROME_LABELS = {
    "search",
    "privacy policy",
    "survey",
    "next",
    "continue",
    "back",
    "skip",
    "close",
    "reload",
    "cashout",
    "balance",
    "featured surveys",
    "more options",
    "accept",
    "reject",
    "select one",
    "select all that apply",
    "help",
    "accessibility statement",
    "accessibility statement - help",
    "continue »",
    "continue >",
    "« back",
    "< back",
    "close button",
    "close this survey",
    "close survey",
    "go back",
}

QUESTION_KB_KEY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("birth date",), "date_of_birth"),
    (("date of birth",), "date_of_birth"),
    (("following counties",), "county"),
    (("which county",), "county"),
    (("occupational group",), "occupation_group"),
    (("chief income earner",), "occupation_group"),
    (("are you?",), "gender"),
    (("where are you living",), "country"),
    (("where do you live",), "country"),
    (("country of residence",), "country"),
    (("which country",), "country"),
    (("which of these pets",), "household_pets"),
    (("pets currently live",), "household_pets"),
    (("pets", "household"), "household_pets"),
    (("pets", "live with you"), "household_pets"),
    (("what is your age",), "age"),
    (("how old are you",), "age"),
    (("your age",), "age"),
    (("annual income",), "household_income"),
    (("household", "income"), "household_income"),
    (("dependent children",), "number_of_children"),
    (("how many", "children"), "number_of_children"),
    (("state their ages",), "child_age"),
    (("their ages",), "child_age"),
    (("child's age",), "child_age"),
    (("enter a whole number",), "child_age"),
)

NONE_TOKENS = {
    "none",
    "no",
    "no pets",
    "no pet",
    "n/a",
    "na",
    "nothing",
    "i do not have any pets",
    "i don't have any pets",
    "do not have any pets",
    "don't have any pets",
}

SKIP_TOKENS = {"skip", "quit", "abort", "exit", "cancel", "stop"}

_STOP_WORDS = {
    "which", "of", "these", "the", "a", "an", "to", "in", "your", "you",
    "with", "currently", "do", "does", "what", "is", "are", "for", "and",
    "or", "on", "at", "this", "that", "live",
}


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("’", "'")).strip()


def option_match_keys(label: str) -> set[str]:
    """Expand a visible option into comparable tokens (Cat(s) -> cat, cats)."""
    text = _normalize_space(label).lower()
    if not text:
        return set()
    keys = {text, re.sub(r"[^a-z0-9]+", "", text)}
    stripped = _normalize_space(re.sub(r"\(s\)", "", text, flags=re.I))
    if stripped:
        keys.add(stripped)
        if not stripped.endswith("s"):
            keys.add(stripped + "s")
        else:
            keys.add(stripped[:-1])
    for inner in re.findall(r"\(([^)]+)\)", text):
        for part in re.split(r"[,/]| etc\.?", inner):
            part = _normalize_space(part).strip(" .")
            if part and part not in {"s", "etc"}:
                keys.add(part)
    stem = re.sub(r"[^a-z0-9 ]+", " ", stripped or text)
    stem = _normalize_space(stem)
    if stem:
        keys.add(stem)
        keys.update(stem.split())
    none_like = (
        "do not have" in text
        or "don't have" in text
        or "no pets" in text
        or text in NONE_TOKENS
    )
    if none_like:
        keys.update(NONE_TOKENS)
    return {key for key in keys if key}


def question_text_from_ocr(ocr_text: str) -> str:
    """Reconstruct the visible question, including wrapped lines before '?'."""
    pieces: list[str] = []
    for raw in str(ocr_text or "").splitlines():
        line = _normalize_space(raw)
        if not line:
            continue
        lowered = line.lower()
        if lowered in OPTION_CHROME_LABELS:
            if pieces:
                break
            continue
        pieces.append(line)
        if "?" in line:
            break
        if len(pieces) >= 6:
            break
    question = _normalize_space(" ".join(pieces))
    if "?" in question:
        question = question[: question.rfind("?") + 1]
        match = re.search(r"([A-Za-z][^?]{6,}\?)", question)
        if match:
            question = _normalize_space(match.group(1))
    return question


def visible_answer_option_labels(
    ocr_text: str,
    node_labels: Optional[list[str]] = None,
) -> list[str]:
    """Collect unique visible answer labels, skipping chrome and the question."""
    labels: list[str] = []
    seen: set[str] = set()
    question = question_text_from_ocr(ocr_text).lower()

    def add(raw: str) -> None:
        label = _normalize_space(repair_ocr_i_am(raw))
        if not label or (len(label) < 2 and not label.isdigit()):
            return
        label = re.sub(r"^[Oo0©]\s+", "", label).strip()
        if not label:
            return
        key = label.lower()
        if key in OPTION_CHROME_LABELS or key in seen:
            return
        if key.endswith("%") or re.fullmatch(r"\d{1,2}:\d{2}", key):
            return
        if "?" in label:
            return
        if question and (key in question or question in key):
            return
        seen.add(key)
        labels.append(label)

    for node_label in node_labels or []:
        add(node_label)

    past_question = False
    for raw in str(ocr_text or "").splitlines():
        line = _normalize_space(raw)
        if not line:
            continue
        lowered = line.lower()
        if not past_question:
            if "?" in line or lowered in OPTION_CHROME_LABELS:
                past_question = True
            continue
        if lowered in OPTION_CHROME_LABELS:
            continue
        add(line)

    return labels


def derive_question_kb_key(
    question: str,
    extra_hints: Optional[dict[str, tuple[str, ...]]] = None,
) -> str:
    """Map a visible question onto a stable knowledge-base key."""
    normalized = _normalize_space(question).lower()
    for hints, key in QUESTION_KB_KEY_HINTS:
        if all(hint in normalized for hint in hints):
            return key
    for key, hints in (extra_hints or {}).items():
        if any(hint in normalized for hint in hints):
            return key
    words = re.findall(r"[a-z0-9]+", normalized)
    kept = [word for word in words if word not in _STOP_WORDS][:6]
    slug = "_".join(kept) or "survey_answer"
    return re.sub(r"[^a-z0-9_]+", "_", slug).strip("_")


def intended_options_from_kb_value(value: Any) -> list[str]:
    """Normalize a stored KB answer into visible option labels."""
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if re.search(r"[,;]", text):
        return [part.strip() for part in re.split(r"[,;]", text) if part.strip()]
    return [text]


def _match_token_to_options(token: str, options: list[str]) -> Optional[str]:
    needle = _normalize_space(token).lower()
    if not needle:
        return None
    numbered = re.match(r"^(?:option|opt|choice|#)\s*(\d+)$", needle)
    if numbered:
        needle = numbered.group(1)
    if needle.isdigit():
        for option in options:
            if re.fullmatch(r"\d+", option.strip()) and str(int(option)) == str(int(needle)):
                return option
        if re.match(r"^(?:option|opt|choice|#)\s*\d+$", _normalize_space(token).lower()):
            index = int(needle) - 1
            if 0 <= index < len(options):
                return options[index]
        numeric_scale = sum(1 for option in options if re.fullmatch(r"\d+", option.strip())) >= 3
        if not numeric_scale:
            index = int(needle) - 1
            if 0 <= index < len(options):
                return options[index]
        return None
    needle_keys = option_match_keys(needle)
    exact: list[str] = []
    partial: list[str] = []
    for option in options:
        option_keys = option_match_keys(option)
        if needle in option_keys or option.lower() == needle:
            exact.append(option)
            continue
        if needle_keys & option_keys:
            exact.append(option)
            continue
        option_blob = " ".join(sorted(option_keys))
        if needle in option.lower() or option.lower() in needle:
            partial.append(option)
        elif any(key in option_blob for key in needle_keys if len(key) >= 3):
            partial.append(option)
    if exact:
        return exact[0]
    if len(partial) == 1:
        return partial[0]
    return None


def parse_human_answer_input(
    raw: str,
    options: list[str],
) -> tuple[str, list[str]]:
    """Parse operator text into grounded option labels.

    Returns (status, labels) where status is:
      ok | skip | empty | unmatched
    """
    text = _normalize_space(raw)
    if not text:
        return "empty", []
    lowered = text.lower()
    if lowered in SKIP_TOKENS:
        return "skip", []

    only_match = re.match(r"^only\s+(.+)$", text, flags=re.I)
    if only_match:
        text = _normalize_space(only_match.group(1))
        lowered = text.lower()

    if lowered in NONE_TOKENS:
        none_option = next(
            (option for option in options if NONE_TOKENS & option_match_keys(option)),
            None,
        )
        if none_option:
            return "ok", [none_option]
        return "unmatched", []

    tokens = [part for part in re.split(r"\s*(?:,|;|&|\band\b)\s*", text) if part]
    if not tokens:
        tokens = [text]

    matched: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        option = _match_token_to_options(token, options)
        if not option:
            continue
        key = option.lower()
        if key in seen:
            continue
        seen.add(key)
        matched.append(option)

    if matched:
        return "ok", matched
    return "unmatched", []


def fallback_keywords_from_question(question: str) -> list[str]:
    normalized = _normalize_space(question).lower()
    if "pets" in normalized and "household" in normalized:
        return ["pets currently live", "household"]
    words = [word for word in re.findall(r"[a-z0-9]+", normalized) if word not in _STOP_WORDS]
    phrases: list[str] = []
    if len(words) >= 2:
        phrases.append(" ".join(words[:3]))
    if words:
        phrases.append(words[0])
    return phrases[:3]


def _load_human_answer_matching():
    """Prefer the sibling module when present; otherwise use the vendored helpers."""
    candidates = [
        Path(__file__).resolve().parent / "human_answer_matching.py",
        BASE_DIR / "human_answer_matching.py",
    ]
    for matching_path in candidates:
        if not matching_path.exists():
            continue
        spec = importlib.util.spec_from_file_location("human_answer_matching", matching_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return None


_HUMAN_ANSWER_MATCHING = _load_human_answer_matching()
if _HUMAN_ANSWER_MATCHING is not None:
    NONE_TOKENS = _HUMAN_ANSWER_MATCHING.NONE_TOKENS
    OPTION_CHROME_LABELS = _HUMAN_ANSWER_MATCHING.OPTION_CHROME_LABELS
    QUESTION_KB_KEY_HINTS = _HUMAN_ANSWER_MATCHING.QUESTION_KB_KEY_HINTS
    SKIP_TOKENS = _HUMAN_ANSWER_MATCHING.SKIP_TOKENS
    derive_question_kb_key = _HUMAN_ANSWER_MATCHING.derive_question_kb_key
    fallback_keywords_from_question = _HUMAN_ANSWER_MATCHING.fallback_keywords_from_question
    intended_options_from_kb_value = _HUMAN_ANSWER_MATCHING.intended_options_from_kb_value
    option_match_keys = _HUMAN_ANSWER_MATCHING.option_match_keys
    question_text_from_ocr = _HUMAN_ANSWER_MATCHING.question_text_from_ocr

OPTION_CHROME_LABELS = set(OPTION_CHROME_LABELS) | {
    "close button", "close this survey", "close survey", "go back",
    "continue »", "continue >", "« back", "< back",
    "select one", "select all that apply", "survey",
}

_QUESTION_TEXT_FROM_OCR_IMPL = question_text_from_ocr


def question_text_from_ocr(ocr_text: str) -> str:
    """Keep the real question; drop clock/battery/Survey header prefixes."""
    question = _QUESTION_TEXT_FROM_OCR_IMPL(ocr_text)
    if "?" in (question or ""):
        clipped = question[: question.rfind("?") + 1]
        match = re.search(r"([A-Za-z][^?]{6,}\?)", clipped)
        if match:
            return _normalize_space(match.group(1))
        return _normalize_space(clipped)
    return question


def canonical_key(key: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", str(key).strip().lower().replace("-", "_"))
    return CANONICAL_ALIASES.get(value, value).strip("_")


def load_kb() -> dict[str, Any]:
    if not KB_FILE.exists():
        return {}
    try:
        raw = json.loads(KB_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
    except Exception as exc:
        logger.error("KB load failed: %s", exc)
        return {}

    clean: dict[str, Any] = {}
    for k, v in raw.items():
        ck = canonical_key(k)
        if ck and v not in (None, ""):
            clean[ck] = v

    # Self-heal aliases/duplicates in the persistent file.
    if clean != raw:
        save_kb(clean)
    return clean


def load_persona() -> dict[str, Any]:
    """Safely read MASTER_USER_PERSONA without executing the Python file."""
    if not PERSONA_FILE.exists():
        logger.warning("Persona file not found: %s", PERSONA_FILE)
        return {}
    try:
        tree = ast.parse(PERSONA_FILE.read_text(encoding="utf-8"), filename=str(PERSONA_FILE))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "MASTER_USER_PERSONA" for target in targets):
                value_node = node.value
                value = ast.literal_eval(value_node)
                if isinstance(value, dict):
                    return value
                raise ValueError("MASTER_USER_PERSONA must be a dictionary")
        logger.warning("MASTER_USER_PERSONA was not found in %s", PERSONA_FILE)
    except Exception as exc:
        logger.error("Persona load failed: %s", exc)
    return {}


def save_kb(kb: dict[str, Any]) -> None:
    tmp = KB_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(kb, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(KB_FILE)
