"""Load the tokenizer, base model and (optionally) the trained adapter from local files."""
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .config import ADAPTER_DIR, BASE_MODEL_DIR


def pick_device():
    return "cuda" if torch.cuda.is_available() else "cpu"


def pick_dtype():
    if not torch.cuda.is_available():
        return torch.float32
    return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16


def load_tokenizer(path=BASE_MODEL_DIR):
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
    # TinyLlama pads with </s>; use <unk> so end-of-answer tokens stay visible to training.
    if tokenizer.pad_token is None or tokenizer.pad_token_id == tokenizer.eos_token_id:
        tokenizer.pad_token = tokenizer.unk_token
    return tokenizer


def load_base_model():
    model = AutoModelForCausalLM.from_pretrained(
        str(BASE_MODEL_DIR), dtype=pick_dtype(), local_files_only=True
    )
    return model.to(pick_device())


def load_coach(adapter_dir=ADAPTER_DIR):
    """Base model + HealthyCoach adapter, ready for chat."""
    from peft import PeftModel

    if not (BASE_MODEL_DIR / "model.safetensors").exists():
        raise FileNotFoundError("Base model missing. Run INSTALL_WINDOWS.bat first.")
    if not (adapter_dir / "adapter_config.json").exists():
        raise FileNotFoundError(f"Adapter missing: {adapter_dir}. Train it with python -m healthbot.train")
    tokenizer = load_tokenizer(adapter_dir)
    model = PeftModel.from_pretrained(load_base_model(), str(adapter_dir))
    model.eval()
    return tokenizer, model
