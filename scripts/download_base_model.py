"""One-time download of the TinyLlama base model into models/base (needs internet)."""
from pathlib import Path

from huggingface_hub import snapshot_download

REPO_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
TARGET = Path(__file__).resolve().parent.parent / "models" / "base"


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {REPO_ID} into {TARGET} ...")
    snapshot_download(repo_id=REPO_ID, local_dir=str(TARGET),
                      allow_patterns=["*.json", "*.safetensors", "tokenizer.model"])
    print("Done. The chatbot can now run offline.")


if __name__ == "__main__":
    main()
