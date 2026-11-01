"""Streaming chat with the HealthyCoach model.

Terminal chat:  .venv\\Scripts\\python.exe -m healthbot.chat
"""
import threading

import torch
from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer

from .loader import load_coach
from .profile import load_profile
from .prompt import build_messages, prompt_text


class _StopWhenSet(StoppingCriteria):
    def __init__(self, event):
        self.event = event

    def __call__(self, input_ids, scores, **kwargs):
        return self.event.is_set()


class Coach:
    def __init__(self, tokenizer, model):
        self.tokenizer = tokenizer
        self.model = model

    @classmethod
    def load(cls):
        return cls(*load_coach())

    @property
    def device_name(self):
        device = next(self.model.parameters()).device
        return torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU"

    def stream(self, question, profile=None, temperature=0.6, max_new_tokens=320, stop_event=None):
        """Yield the growing answer text. Setting stop_event ends generation early."""
        note = profile.note_for_model() if profile else ""
        text = prompt_text(self.tokenizer, build_messages(question, profile_note=note))
        inputs = self.tokenizer(text, return_tensors="pt", add_special_tokens=False).to(self.model.device)
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        kwargs = dict(
            **inputs, streamer=streamer, max_new_tokens=max_new_tokens,
            do_sample=temperature > 0, temperature=max(temperature, 1e-3), top_p=0.9,
            repetition_penalty=1.1, pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
        )
        if stop_event is not None:
            kwargs["stopping_criteria"] = StoppingCriteriaList([_StopWhenSet(stop_event)])

        def run():
            with torch.inference_mode():
                self.model.generate(**kwargs)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        answer = ""
        for piece in streamer:
            answer += piece
            yield answer
        worker.join()

    def answer(self, question, profile=None, **options):
        result = ""
        for result in self.stream(question, profile, **options):
            pass
        return result.strip()


def main():
    print("Loading HealthyCoach...")
    coach = Coach.load()
    profile = load_profile()
    print(f"Ready on {coach.device_name}. Profile: {'loaded' if profile else 'none'}. Type 'exit' to quit.")
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue
        print("\nCoach: ", end="", flush=True)
        shown = 0
        for text in coach.stream(question, profile):
            print(text[shown:], end="", flush=True)
            shown = len(text)
        print()


if __name__ == "__main__":
    main()
