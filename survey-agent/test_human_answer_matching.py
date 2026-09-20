#!/usr/bin/env python3
"""v24.0.17 regression: pets household key-in without ADB."""

from human_answer_matching import (
    derive_question_kb_key,
    intended_options_from_kb_value,
    parse_human_answer_input,
    question_text_from_ocr,
    visible_answer_option_labels,
)

PETS_OCR = """Which of these pets currently live with you in your
household?
Search
Amphibians (frogs, toads, etc.)
Bird(s)
Cat(s)
Dog(s)
Fish
Horse(s)
I do not have any pets
Privacy Policy
"""


def main() -> int:
    question = question_text_from_ocr(PETS_OCR)
    options = visible_answer_option_labels(PETS_OCR)
    key = derive_question_kb_key(question)
    cat_dog_fish = parse_human_answer_input("Cat, Dog, Fish", options)
    only_fish = parse_human_answer_input("only Fish", options)
    none_status, none_labels = parse_human_answer_input("none", options)
    skip_status, _ = parse_human_answer_input("skip", options)
    numbered = parse_human_answer_input("3, 4, 5", options)
    stored = intended_options_from_kb_value(["Cat(s)", "Dog(s)", "Fish"])

    checks = {
        "question": "pets currently live" in question.lower() and question.endswith("?"),
        "options_cat": "Cat(s)" in options,
        "options_dog": "Dog(s)" in options,
        "options_fish": "Fish" in options,
        "options_none": any("do not have any pets" in item.lower() for item in options),
        "no_search": "Search" not in options,
        "no_privacy": not any("privacy" in item.lower() for item in options),
        "kb_key": key == "household_pets",
        "cat_dog_fish": cat_dog_fish == ("ok", ["Cat(s)", "Dog(s)", "Fish"]),
        "only_fish": only_fish == ("ok", ["Fish"]),
        "none": none_status == "ok" and none_labels and "pets" in none_labels[0].lower(),
        "skip": skip_status == "skip",
        "numbered": numbered == ("ok", ["Cat(s)", "Dog(s)", "Fish"]),
        "stored": stored == ["Cat(s)", "Dog(s)", "Fish"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print("FAILED:", failed)
        print("question=", question)
        print("options=", options)
        print("cat_dog_fish=", cat_dog_fish)
        print("only_fish=", only_fish)
        print("none=", none_status, none_labels)
        print("numbered=", numbered)
        return 1
    print("human_answer_matching pets regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
