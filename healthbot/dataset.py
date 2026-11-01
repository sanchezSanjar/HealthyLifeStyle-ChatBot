"""Build the healthy-lifestyle training set from a general instruction dataset.

Keeps only examples about nutrition, fitness, sleep, stress, hydration and healthy habits,
drops off-topic matches (e.g. "team-building exercise") and very short answers, and writes
data/health_instructions.jsonl.

Run:  .venv\\Scripts\\python.exe -m healthbot.dataset
"""
import json
import re
from collections import Counter

from .config import DATA_FILE, SOURCE_DATASET

TOPICS = {
    "nutrition": r"\b(nutrition|nutrient|diet|healthy (food|eating|meal|snack|breakfast|lunch|dinner|recipe)"
                 r"|vegetable|fruit|protein|vitamin|calorie|fiber|whole grain|sugar intake|balanced meal)\w*",
    "fitness": r"\b(exercise|workout|fitness|cardio|strength training|stretching|yoga|jogging"
               r"|physical activity|muscle|push-?up|squat)\w*",
    "sleep": r"\b(sleep|insomnia|bedtime|nap)\w*",
    "stress": r"\b(stress|anxiety|meditation|mindfulness|mental health|relaxation|burnout)\w*",
    "hydration": r"\b(hydrat|drink(ing)? (more )?water|water intake)\w*",
    "habits": r"\b(healthy (lifestyle|habit|living|weight)|lose weight|weight loss|wellness|well-?being)\w*",
}
# Matches that look healthy but are about something else.
EXCLUDE = re.compile(
    r"team[- ]?building|writing exercise|math|equation|code|program|python|sql|function|"
    r"poem|haiku|story|song|lyric|tweet|slogan|advertis|translate|grammar|sentence|"
    r"rewrite|paraphrase|classify|synonym|antonym|headline|title|rhyme|essay|"
    r"placeholder|placelholder|fill in|blank|alphabetical|spell",
    re.I,
)
MIN_ANSWER_CHARS = 60


def topic_of(text):
    for name, pattern in TOPICS.items():
        if re.search(pattern, text, re.I):
            return name
    return None


def build():
    from datasets import load_dataset

    rows = load_dataset(SOURCE_DATASET, split="train")
    kept, seen = [], set()
    for row in rows:
        question = f"{row['instruction']} {row['input']}".strip()
        topic = topic_of(question)
        if topic is None or EXCLUDE.search(question):
            continue
        if len(row["output"].strip()) < MIN_ANSWER_CHARS:
            continue
        key = row["instruction"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append({"topic": topic, "instruction": row["instruction"].strip(),
                     "input": row["input"].strip(), "output": row["output"].strip()})

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        for item in kept:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    counts = Counter(item["topic"] for item in kept)
    print(f"Kept {len(kept)} of {len(rows)} examples -> {DATA_FILE}")
    for name, count in counts.most_common():
        print(f"  {name:<10} {count}")
    return kept


def load_examples():
    with open(DATA_FILE, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    build()
