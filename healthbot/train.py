"""Fine-tune a LoRA adapter for HealthyCoach on the healthy-lifestyle dataset (GPU).

Loss is computed on the answer only, not on the system prompt or the question.

Run:  .venv\\Scripts\\python.exe -m healthbot.train
      .venv\\Scripts\\python.exe -m healthbot.train --max-samples 40 --epochs 1   (quick check)
"""
import argparse
import json
import math
import random
import time

import torch
from peft import LoraConfig, get_peft_model
from transformers import Trainer, TrainingArguments

from .config import ADAPTER_DIR, CHECKPOINT_DIR, SOURCE_DATASET
from .dataset import load_examples
from .loader import load_base_model, load_tokenizer
from .prompt import training_texts


def encode(tokenizer, example, max_length):
    prompt, answer = training_texts(tokenizer, example)
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
    input_ids = (prompt_ids + answer_ids)[:max_length]
    labels = ([-100] * len(prompt_ids) + answer_ids)[:max_length]
    return {"input_ids": input_ids, "labels": labels}


class PadCollator:
    def __init__(self, pad_id):
        self.pad_id = pad_id

    def __call__(self, batch):
        width = max(len(item["input_ids"]) for item in batch)
        ids, labels, mask = [], [], []
        for item in batch:
            gap = width - len(item["input_ids"])
            ids.append(item["input_ids"] + [self.pad_id] * gap)
            labels.append(item["labels"] + [-100] * gap)
            mask.append([1] * len(item["input_ids"]) + [0] * gap)
        return {"input_ids": torch.tensor(ids), "labels": torch.tensor(labels),
                "attention_mask": torch.tensor(mask)}


def main():
    parser = argparse.ArgumentParser(description="Train the HealthyCoach LoRA adapter.")
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--max-samples", type=int, default=0, help="0 = use all examples")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        print("Warning: no GPU found. Training on CPU will be very slow.")

    examples = load_examples()
    random.Random(42).shuffle(examples)
    if args.max_samples:
        examples = examples[:args.max_samples]
    split = max(1, int(len(examples) * 0.05))
    eval_rows, train_rows = examples[:split], examples[split:]

    tokenizer = load_tokenizer()
    train_set = [encode(tokenizer, row, args.max_length) for row in train_rows]
    eval_set = [encode(tokenizer, row, args.max_length) for row in eval_rows]
    print(f"Training on {len(train_set)} examples, evaluating on {len(eval_set)}")

    model = load_base_model()
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model.config.use_cache = False
    lora = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    use_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    steps_per_epoch = math.ceil(len(train_set) / (args.batch_size * args.grad_accum))
    warmup = max(1, int(0.05 * steps_per_epoch * args.epochs))
    training_args = TrainingArguments(
        output_dir=str(CHECKPOINT_DIR),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=warmup,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="no",
        bf16=use_bf16,
        fp16=torch.cuda.is_available() and not use_bf16,
        report_to="none",
        remove_unused_columns=False,
    )
    trainer = Trainer(model=model, args=training_args, train_dataset=train_set,
                      eval_dataset=eval_set, data_collator=PadCollator(tokenizer.pad_token_id))

    started = time.time()
    result = trainer.train()
    minutes = (time.time() - started) / 60

    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ADAPTER_DIR))
    tokenizer.save_pretrained(str(ADAPTER_DIR))

    evals = [log for log in trainer.state.log_history if "eval_loss" in log]
    report = {
        "source_dataset": SOURCE_DATASET,
        "train_examples": len(train_set),
        "eval_examples": len(eval_set),
        "epochs": args.epochs,
        "lora": {"r": lora.r, "alpha": lora.lora_alpha, "target_modules": sorted(lora.target_modules)},
        "learning_rate": args.lr,
        "train_loss": round(result.training_loss, 4),
        "eval_loss_per_epoch": [round(log["eval_loss"], 4) for log in evals],
        "minutes": round(minutes, 1),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
    }
    with open(ADAPTER_DIR / "training_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
