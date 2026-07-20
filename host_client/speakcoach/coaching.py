"""Job B cold path: analyze mistakes, explain, TTS read-back, log to SQLite.

A dedicated terminal session — latency is acceptable here, unlike dictation.
"""

from .asr_client import ASRClient
from .audio import Recorder, play, rms
from .config import Config
from .db import insert_mistakes, log_utterance, update_utterance_cleaned
from .dictation import SILENCE_RMS
from .llm_client import LLMClient
from .tts_client import TTSClient

SEVERITY_MARKS = {1: "·", 2: "••", 3: "‼"}


def run_practice(config: Config) -> None:
    asr = ASRClient(config)
    llm = LLMClient(config)
    tts = TTSClient(config)

    print(f"SpeakCoach practice (coach model: {llm.model})")
    print("Speak a sentence or two per round; I'll correct, explain, and read back.")
    print("Press Enter to start recording, Enter again to stop. Ctrl+C to quit.")

    while True:
        try:
            input("\n[practice] Enter to record > ")
            rec = Recorder()
            rec.start()
            input("[recording] Enter to stop > ")
            wav = rec.stop()
        except (KeyboardInterrupt, EOFError):
            print("\nGood session. See you next time!")
            return

        if len(wav) < 1000 or rms(wav) < SILENCE_RMS:
            print("(no speech captured)")
            continue

        raw = asr.transcribe(wav)["text"]
        if not raw:
            print("(silence)")
            continue
        print(f"\n  you said: {raw}")

        # the utterance is logged even if analysis fails afterwards
        utterance_id = log_utterance(config.db_path, "practice", raw, None)

        print("  (analyzing...)")
        try:
            analysis = llm.analyze_mistakes(raw)
        except RuntimeError as e:
            print(f"  analysis failed: {e}")
            continue

        corrected = analysis["corrected"]
        native = analysis["native_alternative"]
        mistakes = analysis["mistakes"]
        update_utterance_cleaned(config.db_path, utterance_id, corrected)

        print(f"\n  corrected: {corrected}")
        if mistakes:
            for i, m in enumerate(mistakes, 1):
                print(f"   {i}. [{m['category']} {SEVERITY_MARKS[m['severity']]}] "
                      f"\"{m['original']}\" → \"{m['correction']}\"")
                print(f"      {m['explanation']}")
        else:
            print("   no real mistakes — nice.")
        if native:
            print(f"  native:    {native}")

        n = insert_mistakes(config.db_path, utterance_id, mistakes)
        if n:
            print(f"  ({n} mistake{'s' if n > 1 else ''} logged)")

        # spoken read-back happens last so reading the feedback isn't delayed
        try:
            readback = corrected if not native or native == corrected \
                else f"{corrected} ... Or more naturally: {native}"
            play(tts.synthesize(readback))
        except Exception as e:
            print(f"  (read-back unavailable: {e})")
