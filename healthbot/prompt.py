"""Chat prompts in TinyLlama's own chat format (<|system|>, <|user|>, <|assistant|>)."""
from .config import SYSTEM_PROMPT


def build_messages(question, profile_note="", extra_input=""):
    system = SYSTEM_PROMPT + (f"\n\n{profile_note}" if profile_note else "")
    user = question.strip() + (f"\n\n{extra_input.strip()}" if extra_input.strip() else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def prompt_text(tokenizer, messages):
    """Prompt up to and including the assistant tag, ready for generation."""
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)


def training_texts(tokenizer, example):
    """(prompt, answer) for one dataset row; the answer ends with </s> so the model learns to stop."""
    messages = build_messages(example["instruction"], extra_input=example.get("input", ""))
    return prompt_text(tokenizer, messages), example["output"].strip() + tokenizer.eos_token
