# Survey engine modules (v24.0.149)

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
| `parts/12b_select_n.py` | Select-up-to-N checkboxes |
| `parts/13_select_one.py` | Select-one radios |
| `parts/14_matrix.py` | Matrix grid |
| `parts/15_progression.py` | Continue/Next, repair |
| `parts/16_inspect.py` | Inspector, KB routers |
| `parts/17_human.py` | Terminal key-in |
| `parts/18_checks_a.py` | Self-checks A |
| `parts/19_checks_b.py` | Self-checks B |
| `parts/20_text_fields.py` | Text-box geometry |
| `parts/20a_form_controls.py` | Fused UI/OCR control map; composite DOB resolver/operator |
| `parts/20b_screen_objects.py` | Screenshot/UI/OCR scene graph and safe coordinate grounding |
| `parts/20c_question_flow.py` | Active-question identity, dynamic page series and footer ownership |
| `parts/20d_required_gate.py` | Required-field transaction and answer-before-navigation gate |
| `parts/20e_screen_semantics.py` | Exact option state and information-page semantics |
| `parts/20f_answer_transaction.py` | Fresh-question detection and verified answer ownership |
| `parts/20g_interaction_contract.py` | Signature-bound final contract after every router and LLM decision |
| `parts/20h_underline_inputs.py` | Pixel grounding for underline-only WebView text/number inputs |
| `parts/21_open_text.py` | Captcha, drag-drop, open text |
| `parts/22_execute.py` | Tap/type/verify |
| `parts/22a_recovery.py` | Failed-action recovery |
| `parts/23_checks_c.py` | Self-checks C |
| `parts/23b_notice_checks.py` | Notice and exact-option regressions |
| `parts/24_preflight.py` | Preflight |
| `parts/25_runner.py` | Observe + main loop |
| `parts/26_reason.py` | Screenshot-first critique and local invariants |
| `parts/27_six_step.py` | Unified map → reason → act → verify → navigate planner |

The final action path is intentionally layered: object map → specialized/local
router or VLM → required-field guard → interaction contract → executor → fresh
post-action observation → exact verification. A question-signature change clears
prior completion state, so a newly revealed item cannot inherit permission to tap
Continue/Next/Submit.

Max 800 lines per part. Monolith archive: `archive/survey_with_salad.v24.0.87.py`.
