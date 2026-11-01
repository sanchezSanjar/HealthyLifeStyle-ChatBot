"""Compare the base model and the HealthyCoach adapter on the held-out examples.

Run:  .venv\\Scripts\\python.exe -m healthbot.evaluate
Writes the result into models/healthy_coach_adapter/training_report.json ("evaluation").
"""
import json
import math
import random

import torch
from peft import PeftModel

from .config import ADAPTER_DIR
from .dataset import load_examples
from .loader import load_base_model, load_tokenizer
from .train import encode


def held_out(tokenizer):
    """Same 5% split as training (seed 42)."""
    examples = load_examples()
    random.Random(42).shuffle(examples)
    split = max(1, int(len(examples) * 0.05))
    return [encode(tokenizer, row, 512) for row in examples[:split]]


@torch.inference_mode()
def answer_loss(model, rows):
    total, tokens = 0.0, 0
    for row in rows:
        ids = torch.tensor([row["input_ids"]], device=model.device)
        labels = torch.tensor([row["labels"]], device=model.device)
        count = int((labels[0, 1:] != -100).sum())
        total += model(input_ids=ids, labels=labels).loss.item() * count
        tokens += count
    return total / tokens


def main():
    tokenizer = load_tokenizer(ADAPTER_DIR)
    rows = held_out(tokenizer)
    model = load_base_model()
    base = answer_loss(model, rows)
    tuned = answer_loss(PeftModel.from_pretrained(model, str(ADAPTER_DIR)), rows)
    result = {
        "held_out_examples": len(rows),
        "base_model_loss": round(base, 4),
        "adapter_loss": round(tuned, 4),
        "base_model_perplexity": round(math.exp(base), 2),
        "adapter_perplexity": round(math.exp(tuned), 2),
    }
    report_file = ADAPTER_DIR / "training_report.json"
    report = json.loads(report_file.read_text(encoding="utf-8"))
    report["evaluation"] = result
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
