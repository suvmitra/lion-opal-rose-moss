# Survey engine modules (v24.0.116)

`python survey_with_salad.py` still starts the agent. Parts are loaded into that
file's namespace so every original function is intact.

| File | Task |
|---|---|
| `parts/00_config.py` | Env, paths, logger |
| `parts/01_changelog.py` | Version changelog |
| `parts/02_runtime.py` | Types, ADB, screenshot, OCR, UI dump |
| `parts/03_labels.py` | Labels, landing/consent/dashboard detectors |
| `parts/04_rank_likert.py` | Ranking, Likert, screen classify |
| `parts/05_kb_match.py` | Tiles, option matching, knowledge base |
| `parts/06_learning.py` | Lessons, learned screens, RL |
| `parts/07_vlm.py` | Salad + Gemini vision |
| `parts/08_landing.py` | Participate/Start, consent, terminal close |
| `parts/09_county.py` | Occupation, county dropdown |
| `parts/10_children.py` | Children count and ages |
| `parts/11_carousel.py` | Carousel rows |
| `parts/12_maxdiff_selectall.py` | MaxDiff, select-all |
| `parts/13_select_one.py` | Select-one radios |
| `parts/14_matrix.py` | Matrix grid |
| `parts/15_progression.py` | Continue/Next, repair |
| `parts/16_inspect.py` | Inspector, KB routers |
| `parts/17_human.py` | Terminal key-in |
| `parts/18_checks_a.py` | Self-checks A |
| `parts/19_checks_b.py` | Self-checks B |
| `parts/20_text_fields.py` | Text-box geometry |
| `parts/20a_form_controls.py` | Fused UI/OCR control map; composite DOB resolver/operator |
| `parts/21_open_text.py` | Captcha, drag-drop, open text |
| `parts/22_execute.py` | Tap/type/verify |
| `parts/23_checks_c.py` | Self-checks C |
| `parts/24_preflight.py` | Preflight |
| `parts/25_runner.py` | Observe + main loop |

Max 800 lines per part. Monolith archive: `archive/survey_with_salad.v24.0.87.py`.
