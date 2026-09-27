# 20h_underline_inputs.py — underline-only WebView input detection

def _underline_input_coords_from_image(image: Any) -> Optional[list[int]]:
    """Find a short underline-only input that has no accessibility node.

    Some survey vendors render ``<input type=number>`` as a 2-6 px dark line.
    It has no surrounding rectangle and UIAutomator exposes only the WebView, so
    rectangle detection and OCR cannot ground it.  A valid candidate is a stable
    horizontal dark run, left aligned, with blank space immediately above it.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    rows: list[tuple[int, int, int]] = []
    min_run = max(24, int(width * 0.075))
    max_run = int(width * 0.82)
    for y in range(int(height * 0.15), int(height * 0.72)):
        start = None
        for x in range(int(width * 0.015), int(width * 0.88)):
            red, green, blue = pixels[x, y]
            dark = max(red, green, blue) <= 110 and max(red, green, blue) - min(red, green, blue) <= 38
            if dark and start is None:
                start = x
            if not dark and start is not None:
                run = x - start
                if min_run <= run <= max_run and start <= int(width * 0.45):
                    rows.append((y, start, x - 1))
                start = None
        if start is not None:
            run = int(width * 0.88) - start
            if min_run <= run <= max_run and start <= int(width * 0.45):
                rows.append((y, start, int(width * 0.88) - 1))
    if not rows:
        return None

    clusters: list[list[tuple[int, int, int]]] = []
    for row in rows:
        compatible = bool(
            clusters
            and row[0] - clusters[-1][-1][0] <= 1
            and abs(row[1] - clusters[-1][-1][1]) <= max(5, int(width * 0.012))
            and abs(row[2] - clusters[-1][-1][2]) <= max(5, int(width * 0.012))
        )
        if compatible:
            clusters[-1].append(row)
        else:
            clusters.append([row])

    ranked: list[tuple[float, list[int]]] = []
    for cluster in clusters:
        thickness = cluster[-1][0] - cluster[0][0] + 1
        if thickness < 2 or thickness > max(18, int(height * 0.015)):
            continue
        line_y = int(sum(row[0] for row in cluster) / len(cluster))
        x1 = int(sum(row[1] for row in cluster) / len(cluster))
        x2 = int(sum(row[2] for row in cluster) / len(cluster))
        rel_y, rel_x, rel_w = line_y / height, x1 / width, (x2 - x1) / width
        # Blank editable area immediately above the baseline distinguishes an
        # input underline from underlined prose and dense text glyphs.
        sample_y1 = max(0, line_y - max(20, int(height * 0.045)))
        sample_y2 = max(sample_y1 + 1, line_y - max(5, int(height * 0.006)))
        dark_pixels, total = 0, 0
        for sy in range(sample_y1, sample_y2, max(1, (sample_y2 - sample_y1) // 12)):
            for sx in range(x1, x2 + 1, max(1, (x2 - x1) // 40)):
                red, green, blue = pixels[sx, sy]
                dark_pixels += int(max(red, green, blue) < 145)
                total += 1
        ink_ratio = dark_pixels / max(1, total)
        if ink_ratio > 0.16:
            continue
        score = rel_w * 8.0 - rel_x * 2.0 - abs(rel_y - 0.30) * 2.0 - ink_ratio * 5.0
        tap_x = int((x1 + x2) / 2)
        tap_y = line_y - max(8, int(height * 0.008))
        ranked.append((score, [int(tap_x * 1000 / width), int(tap_y * 1000 / height)]))
    return max(ranked, key=lambda item: item[0])[1] if ranked else None


def underline_text_input_coords(obs: Observation) -> Optional[list[int]]:
    path = str(obs.screenshot or "")
    if not path or not Path(path).exists():
        return None
    try:
        with Image.open(path) as image:
            coords = _underline_input_coords_from_image(image)
        if coords:
            logger.info("[TEXT FIELD] Underline-only input milli=%s", coords)
        return coords
    except Exception as exc:
        logger.debug("Underline input detection unavailable: %s", exc)
        return None


def underline_input_regression_self_check() -> bool:
    """The detector must prefer a short input underline over bars/buttons."""
    image = Image.new("RGB", (1000, 2000), "white")
    pixels = image.load()
    # Decorative progress bar and a wide CTA must not become text fields.
    for y in range(270, 278):
        for x in range(210, 720):
            pixels[x, y] = (185, 185, 185)
    for y in range(610, 690):
        for x in range(20, 980):
            pixels[x, y] = (8, 28, 25)
    # The actual underline-only field, matching the attached vendor layout.
    for y in range(492, 497):
        for x in range(24, 166):
            pixels[x, y] = (5, 35, 32)
    coords = _underline_input_coords_from_image(image)
    passed = bool(coords and 70 <= coords[0] <= 130 and 220 <= coords[1] <= 250)
    if passed:
        logger.info("[SELF-CHECK] Underline-only input grounded at %s.", coords)
    else:
        logger.error("[SELF-CHECK] Underline-only input grounding failed: %s", coords)
    return passed
