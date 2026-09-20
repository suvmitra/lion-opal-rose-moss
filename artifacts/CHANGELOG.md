# Survey automation changelog

Version history lives in `survey_with_salad.py` (`CHANGELOG` dict) as well as here.
v24.0.16 is archived at `archive/survey_with_salad.v24.0.16.py`.

## 24.0.17

- Do not exit when the VLM is silent or returns `request_human` on a personal question.
- Prompt on the terminal for operator key-in (`Cat, Dog, Fish`, `only Fish`, `none`, numbered rows, or `skip`).
- Write the grounded answer into `knowledge_base.json`, including `personal_question_fallbacks`.
- Re-check the current screen and tick every matching visible option, one atomic action per cycle.
- Reuse stored multi-select answers on later cycles and later runs without re-prompting.
- Pets-household regression fixture matching the supplied checkbox screen.
- New sibling module `human_answer_matching.py` (stdlib-only). Keep it next to the runner.

## 24.0.16

Preserved unchanged in `archive/survey_with_salad.v24.0.16.py`.
