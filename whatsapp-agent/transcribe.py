# Local Hebrew speech-to-text — FALLBACK only. The bridge uses Groq first (fast, free tier)
# and falls back to this when there's no GROQ_API_KEY or Groq fails. Nothing leaves the PC.
# Usage: python transcribe.py <audio file>  → prints the transcript (UTF-8)
# Model: ivrit-ai Whisper large-v3-turbo (CTranslate2, int8 on CPU).
# NOTE: ctranslate2 4.8.x segfaults on this PC — keep ctranslate2==4.5.0 (+ setuptools<81, av<14).
import os
import sys

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
from faster_whisper import WhisperModel

MODEL = os.environ.get("WHISPER_MODEL", "ivrit-ai/whisper-large-v3-turbo-ct2")


def main() -> None:
    model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    # vad_filter=True segfaults here (onnxruntime + ctranslate2 clash) — leave it off
    segments, _ = model.transcribe(sys.argv[1], language="he", beam_size=1)
    text = " ".join(s.text.strip() for s in segments).strip()
    sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    main()
