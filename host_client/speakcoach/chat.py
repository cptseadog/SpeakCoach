"""Chat mode: open-ended conversation practice with a local or API LLM.

Voice-first (speak a turn, hear + read the reply) with a --text REPL. The
partner stays purely conversational by default; --correct makes it open
replies by naturally recasting erroneous sentences (recast technique).
On Ctrl+C the session wraps up: every user turn goes through the local coach
(mistakes feed the same DB as practice mode, so lessons learn from chats),
and the chat model writes a short session note.
"""

import time

from .asr_client import ASRClient
from .audio import Recorder, play, rms
from .chat_client import ApiChatClient
from .config import Config
from .db import (
    create_chat_session,
    end_chat_session,
    insert_chat_message,
    insert_mistakes,
    learner_profile,
    log_utterance,
    update_utterance_cleaned,
)
from .dictation import SILENCE_RMS
from .llm_client import LLMClient
from .tts_client import TTSClient

BASE_PERSONA = """\
You are a friendly, curious native speaker of American English having a relaxed \
voice conversation with a motivated English learner. Their goal is spoken fluency.

About this learner: {profile}

Rules:
- Talk like a real conversation partner, not a teacher. Never lecture about grammar.
- Keep replies short and natural — 2 to 4 sentences — because they are read aloud.
- Use vocabulary slightly above the learner's level so they grow, but stay clear.
- Show genuine interest: react to what they say and ask a follow-up question to \
keep them talking. Let them do most of the talking.\
"""

RECAST_RULE = """
- Recast technique: when the learner's sentence contains a clear error, begin \
your reply by naturally using their sentence in its correct form (as a native \
speaker would echo it), then continue the conversation. Do not explain the \
correction or point it out."""

NO_CORRECT_RULE = """
- Never correct or comment on the learner's English, even implicitly. Just talk."""

SUMMARY_REQUEST = """\
The conversation is over. As the learner's coach, write a short session note \
(under 120 words, plain text) addressed directly to the learner: what you two \
talked about, one thing they did well, and the two or three most important \
recurring language issues they should work on next."""

MAX_HISTORY_MESSAGES = 24  # keep system + recent turns within local context limits


class _LocalChat:
    """Adapter giving LLMClient the same send() shape as ApiChatClient."""

    def __init__(self, llm: LLMClient, model: str | None):
        self.llm = llm
        self.model = model or llm.model

    def send(self, messages: list[dict]) -> str:
        return self.llm.chat(messages, model=self.model)


def _trimmed(messages: list[dict]) -> list[dict]:
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages
    return [messages[0]] + messages[-(MAX_HISTORY_MESSAGES - 1):]


def run_chat(
    config: Config,
    use_api: bool = False,
    text_mode: bool = False,
    correct: bool = False,
    model_override: str | None = None,
) -> None:
    backend = "api" if (use_api or config.chat_backend == "api") else "local"
    llm_local = LLMClient(config)
    if backend == "api":
        partner = ApiChatClient(config, model=model_override)
    else:
        partner = _LocalChat(llm_local, model_override)

    asr = ASRClient(config) if not text_mode else None
    tts = TTSClient(config) if not text_mode else None

    profile = learner_profile(config.db_path)
    system = BASE_PERSONA.format(profile=profile) + (RECAST_RULE if correct else NO_CORRECT_RULE)
    messages: list[dict] = [{"role": "system", "content": system}]
    user_turns: list[tuple[int | None, str]] = []

    session_id = create_chat_session(config.db_path, backend, partner.model, correct)
    print(f"SpeakCoach chat — {backend} model: {partner.model}"
          + (", recast corrections on" if correct else "") + (", text mode" if text_mode else ""))
    print("Ctrl+C ends the session and runs the analysis.\n")

    try:
        while True:
            if text_mode:
                text = input("you > ").strip()
                if not text:
                    continue
            else:
                input("[chat] Enter to record > ")
                rec = Recorder()
                rec.start()
                input("[recording] Enter to stop > ")
                wav = rec.stop()
                if len(wav) < 1000 or rms(wav) < SILENCE_RMS:
                    print("(no speech captured)")
                    continue
                text = asr.transcribe(wav)["text"]
                if not text:
                    print("(silence)")
                    continue
                print(f"you > {text}")

            utterance_id = log_utterance(config.db_path, "chat", text, None)
            insert_chat_message(config.db_path, session_id, "user", text, utterance_id)
            user_turns.append((utterance_id, text))
            messages.append({"role": "user", "content": text})

            t0 = time.monotonic()
            try:
                reply = partner.send(_trimmed(messages))
            except RuntimeError as e:
                print(f"(chat backend error: {e})")
                messages.pop()  # keep history consistent with what the model saw
                continue
            messages.append({"role": "assistant", "content": reply})
            insert_chat_message(config.db_path, session_id, "assistant", reply)

            print(f"partner ({time.monotonic() - t0:.1f}s) > {reply}\n")
            if tts is not None:
                try:
                    play(tts.synthesize(reply))
                except Exception as e:
                    print(f"(read-aloud unavailable: {e})")
    except (KeyboardInterrupt, EOFError):
        pass

    _wrap_up(config, llm_local, partner, session_id, messages, user_turns)


def _wrap_up(config, llm_local, partner, session_id, messages, user_turns) -> None:
    if not user_turns:
        end_chat_session(config.db_path, session_id, None)
        print("\n(no conversation happened — nothing to analyze)")
        return

    print(f"\n\nSession over — analyzing your {len(user_turns)} turn(s) with the local coach...")
    total_mistakes = 0
    for utterance_id, text in user_turns:
        try:
            analysis = llm_local.analyze_mistakes(text)
        except RuntimeError as e:
            print(f"  (analysis failed for one turn: {e})")
            continue
        update_utterance_cleaned(config.db_path, utterance_id, analysis["corrected"])
        total_mistakes += insert_mistakes(config.db_path, utterance_id, analysis["mistakes"])
    print(f"  {total_mistakes} mistake(s) logged — they'll feed your daily lessons.")

    summary = None
    try:
        summary = partner.send(_trimmed(messages) + [{"role": "user", "content": SUMMARY_REQUEST}])
    except RuntimeError as e:
        print(f"  (session summary unavailable: {e})")
    end_chat_session(config.db_path, session_id, summary)
    if summary:
        print(f"\n--- session note ---\n{summary}")
