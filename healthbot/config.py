"""Project paths and names shared by every module."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_MODEL_DIR = ROOT / "models" / "base"
ADAPTER_DIR = ROOT / "models" / "healthy_coach_adapter"
CHECKPOINT_DIR = ROOT / "models" / "checkpoints"
DATA_FILE = ROOT / "data" / "health_instructions.jsonl"
PROFILE_FILE = ROOT / "profile.json"

SOURCE_DATASET = "yahma/alpaca-cleaned"  # CC BY 4.0

SYSTEM_PROMPT = (
    "You are HealthyCoach, a friendly assistant for healthy lifestyle: nutrition, "
    "exercise, sleep, stress and hydration. Give clear, practical and safe advice. "
    "You are not a doctor; for medical problems suggest seeing a professional."
)
