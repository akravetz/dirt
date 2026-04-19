"""Voice channel — always-on mic/speaker harness for the grow assistant.

Listens on the Jabra SPEAK 410 for the "hey Claudia" wake word, then spins up
a Pipecat pipeline that streams the conversation (STT → Claude → TTS). When
the conversation idles out, the pipeline tears down and the wake-word loop
resumes.

Architecture (ADR 005): this is the `voice` channel adapter. Runs as the
`dirt-harness` user. Session transcripts are appended to
`sessions/voice/YYYY-MM-DD.jsonl`; the agent reads them on demand.

Run as a module:
    uv run python -m dirt.channels.voice

Required environment (in `.env`):
    DEEPGRAM_API_KEY, ANTHROPIC_API_KEY, ELABS_API_KEY, ELABS_VOICE_ID

Hardware: the Jabra SPEAK 410 is mic-in 16 kHz mono / speaker-out 48 kHz
stereo. See `wiki/hardware/jabra.md` for the full device quirks encoded in
`_audio_transport.SoundDeviceTransport`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import sys
import time
import uuid
import wave
from collections import deque
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from loguru import logger
from openwakeword.model import Model
from pipecat.adapters.schemas.tools_schema import FunctionSchema, ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_text_processor import LLMTextProcessor
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.utils.text.pattern_pair_aggregator import (
    MatchAction,
    PatternPairAggregator,
)

from dirt_voice.channels._audio_transport import (
    SoundDeviceTransport,
    SoundDeviceTransportParams,
)
from dirt_voice.channels._observers import FrameFlowObserver
from dirt_shared.config import settings
from dirt_shared.observability import CONVERSATION_ID, log_event
from dirt_shared.services.grow_state import grow_week
from dirt_voice.tools import SHARED_TOOLS, ToolSpec

# voice.py lives at apps/voice/src/dirt_voice/channels/voice.py
#   parents[0] channels
#   parents[1] dirt_voice
#   parents[2] src
#   parents[3] voice
#   parents[4] apps
#   parents[5] <repo root>
REPO_ROOT = Path(__file__).resolve().parents[5]

# Written on startup, unlinked on clean shutdown. `kill $(cat var/logs/voice.pid)`
# always targets the actual Python PID — no pattern-matching, no uv wrapper
# confusion, no risk of pkill matching its own shell.
PID_FILE = settings.data_dir / "logs" / "voice.pid"

# Wake model — trained on user-voice ElevenLabs clones + captured RIRs.
# See wiki/decisions/2026-04-16-wake-word-training-strategy.md.
# Lives at <repo>/debug/hey_claudia.onnx (gitignored scratch dir; the .onnx
# file is a trained artifact we keep on disk but not in git).
WAKE_MODEL_PATH = REPO_ROOT / "debug" / "hey_claudia.onnx"
WAKE_SAMPLE_RATE = 16000
WAKE_CHUNK_SAMPLES = int(WAKE_SAMPLE_RATE * 0.08)   # 80 ms
WAKE_THRESHOLD = 0.6
WAKE_NEAR_MISS_FLOOR = 0.1   # temporary: log sub-threshold scores to calibrate
WAKE_AUDIO_CAPTURE_FLOOR = 0.3   # save WAV when score is in ambiguous zone
WAKE_DEBOUNCE_S = 3.0
WAKE_WARMUP_FRAMES = 12   # ~1s at 80ms/frame — drop post-conversation echo tail

# Ring buffer of recent audio frames for hard-negative harvesting. 24 frames
# * 80 ms = ~1.9 s of context, enough to capture the full wake-phrase window
# regardless of where within the frame the peak score lands.
WAKE_AUDIO_BUFFER_FRAMES = 24
WAKE_AUDIO_DIR = Path(__file__).resolve().parents[3] / "logs" / "wake_audio"

# Jabra SPEAK 410 hardware constraints
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 48000     # firmware clock
OUTPUT_CHANNELS = 2            # stereo-only playback endpoint
PLAYBACK_GAIN_DB = 12.0

SESSION_IDLE_TIMEOUT_S = 15

SESSIONS_DIR = settings.data_dir / "sessions" / "voice"

CLAUDIA_SYSTEM_PROMPT_BASE = (
    "Your name is Claudia. You are a warm, confident, sassy 28-year-old "
    "Colombian woman who speaks with natural charm and a little playful "
    "flirtation. You mix the occasional Spanish expression into English "
    "('ay', 'querido', 'de verdad', 'mi amor') but the conversation is "
    "mostly English. You are speaking aloud in a real-time voice "
    "conversation, so: no emojis, no bullet points, no markdown — just "
    "natural spoken sentences. Never write <thinking> blocks, XML tags, "
    "or any meta-commentary about how you're composing your response "
    "(everything you write is spoken aloud verbatim). Keep replies short "
    "(one or two sentences) unless asked for more. Don't over-apologize; "
    "be direct and a little bit cheeky.\n\n"
    "You're helping someone take care of their indoor cannabis grow. You "
    "have three tools available:\n"
    "- get_current_status: latest sensor readings + in-range / out-of-range "
    "flags. Use for 'how are things looking' questions.\n"
    "- get_sensor_trend: trend of a single sensor over N hours. Use for "
    "'how has humidity been today' style questions.\n"
    "- ask_wiki: delegate a question to a research sub-agent that reads the "
    "grow wiki. Use for 'when do I top', 'what's next', schedule / technique "
    "questions, past decisions. It takes a couple seconds, so say one brief "
    "acknowledgment in your voice first — something like 'ay, dame un "
    "segundito', 'a ver, a ver', 'déjame ver', 'espérate', or 'un momentico, "
    "querido'. Pick whatever feels natural; never leave silence while the "
    "tool is running.\n\n"
    "When you don't know something and no tool fits, say so plainly."
)


async def _build_claudia_system_prompt() -> str:
    # Date and grow week change over time; rebuild per conversation so the
    # model always has current context. Short addendum — no effect on cache
    # because Anthropic prompt-cache TTL (≤1h) is shorter than the daily
    # refresh rate anyway.
    return (
        f"{CLAUDIA_SYSTEM_PROMPT_BASE}\n\n"
        f"Today is {date.today().isoformat()}. "
        f"We're in week {await grow_week()} of the grow."
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _session_log_path() -> Path:
    return SESSIONS_DIR / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl"


def _log_event(event: dict) -> None:
    """Append one JSON line to today's session log."""
    event.setdefault("ts", _utc_now())
    with _session_log_path().open("a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _to_pipecat_schema(spec: ToolSpec) -> FunctionSchema:
    return FunctionSchema(
        name=spec.name,
        description=spec.description,
        properties=spec.properties,
        required=spec.required,
    )


def _register_tools(llm: AnthropicLLMService, specs: list[ToolSpec]) -> None:
    """Adapt ToolSpec handlers (async **kwargs -> dict) to Pipecat's callback
    convention, and register them on the LLM service."""
    for spec in specs:
        llm.register_function(
            spec.name,
            _make_pipecat_handler(spec),
            cancel_on_interruption=spec.cancel_on_interruption,
            timeout_secs=spec.timeout_secs,
        )


def _make_pipecat_handler(spec: ToolSpec):
    async def handler(params):
        args = params.arguments or {}
        try:
            result = await spec.handler(**args)
        except Exception as e:
            logger.exception(f"tool {spec.name} failed")
            result = {"error": f"{type(e).__name__}: {e}"}
        await params.result_callback(result)

    return handler


def find_jabra() -> int:
    for i, d in enumerate(sd.query_devices()):
        if "jabra" in d["name"].lower() and d["max_input_channels"] > 0:
            return i
    sys.exit("Jabra not found — is it plugged in?")


_wake_model: Model | None = None
_wake_model_name: str | None = None


def _load_wake_model() -> tuple[Model, str]:
    """Load the wake-word model once; reuse across conversations. Loading the
    ONNX graph + melspec + embedding models is several hundred ms, so we cache."""
    global _wake_model, _wake_model_name
    if _wake_model is None:
        if not WAKE_MODEL_PATH.exists():
            sys.exit(f"Wake model not found at {WAKE_MODEL_PATH}")
        _wake_model = Model(wakeword_model_paths=[str(WAKE_MODEL_PATH)])
        _wake_model_name = next(iter(_wake_model.models.keys()))
    assert _wake_model_name is not None
    return _wake_model, _wake_model_name


def _save_wake_audio_clip(
    frames: deque[np.ndarray], score: float, label: str,
) -> None:
    """Dump the recent audio buffer as WAV for hard-negative harvesting.

    Files land in `logs/wake_audio/` as
    `<ts>_<label>_score-<N.NNN>.wav`. Ops must rotate this directory
    manually — we want to accumulate over weeks to build a real in-situ
    hard-negative set for the next wake-model training run, so automatic
    retention would defeat the purpose.
    """
    WAKE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3]
    path = WAKE_AUDIO_DIR / f"{ts}_{label}_score-{score:.3f}.wav"
    audio_bytes = b"".join(f.tobytes() for f in frames)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(WAKE_SAMPLE_RATE)
        w.writeframes(audio_bytes)


async def wait_for_wake(device: int) -> float:
    """Listen until 'hey Claudia' fires. Returns the detection score."""
    model, model_name = _load_wake_model()
    # openwakeword carries ~1.5s of internal mel/embedding state across calls.
    # Without this, stale features from the prior conversation (plus TTS tail
    # bleeding through the Jabra during stream switchover) produce phantom
    # wakes ~170ms after the pipeline tears down.
    model.reset()

    loop = asyncio.get_running_loop()
    q: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=50)

    def cb(indata, frames, time_info, status):
        if status:
            logger.debug(f"[wake mic] {status}")
        frame = np.frombuffer(bytes(indata), dtype=np.int16).copy()
        with contextlib.suppress(Exception):
            loop.call_soon_threadsafe(q.put_nowait, frame)

    logger.info("listening for 'hey Claudia'…")
    with sd.RawInputStream(
        samplerate=WAKE_SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=WAKE_CHUNK_SAMPLES,
        device=device,
        callback=cb,
    ):
        last_fire = 0.0
        frames_seen = 0
        # Ring buffer of recent audio; on interesting scores we dump it to
        # a WAV for later hard-negative training data.
        recent_frames: deque[np.ndarray] = deque(maxlen=WAKE_AUDIO_BUFFER_FRAMES)
        while True:
            frame = await q.get()
            recent_frames.append(frame)
            # openwakeword returns numpy.float32 — coerce to native Python
            # here so nothing downstream (logging, return value) has to.
            score = float(model.predict(frame)[model_name])
            frames_seen += 1
            # Skip the first ~1s (12 x 80ms frames). Echo tail from the prior
            # TTS response can still be in the Jabra's capture path when the
            # mic reopens, and openwakeword needs ~1.5s of fresh audio to
            # refill its feature buffers before predictions are meaningful.
            if frames_seen <= WAKE_WARMUP_FRAMES:
                continue
            now = time.monotonic()
            if score >= WAKE_THRESHOLD and (now - last_fire) >= WAKE_DEBOUNCE_S:
                last_fire = now
                logger.info(f"wake detected (score={score:.3f})")
                log_event(
                    "wake_scores", "wake_detected",
                    score=round(score, 4),
                    threshold=WAKE_THRESHOLD,
                )
                # Save the positive example too — retraining wants real
                # in-situ positives as much as hard negatives.
                _save_wake_audio_clip(recent_frames, score, "wake")
                return score
            elif score >= WAKE_NEAR_MISS_FLOOR:
                # Sub-threshold scores that plausibly contain speech-like
                # content. Useful for calibrating WAKE_THRESHOLD against
                # real-world conditions. See logs/wake_scores/.
                log_event(
                    "wake_scores", "near_miss",
                    score=round(score, 4),
                    threshold=WAKE_THRESHOLD,
                    floor=WAKE_NEAR_MISS_FLOOR,
                )
                # Capture audio in the ambiguous zone only — the model was
                # uncertain, and a human-labeled version of these is the
                # best hard-negative corpus for the next training run.
                # Scores below 0.3 are mostly noise/silence, not worth
                # hoarding.
                if score >= WAKE_AUDIO_CAPTURE_FLOOR:
                    _save_wake_audio_clip(recent_frames, score, "near_miss")


async def run_conversation(device: int) -> LLMContext:
    """Build and run a single Pipecat conversation session. Returns the final
    LLMContext so the caller can persist the transcript to the session log."""
    transport = SoundDeviceTransport(SoundDeviceTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_sample_rate=INPUT_SAMPLE_RATE,
        audio_out_sample_rate=OUTPUT_SAMPLE_RATE,
        audio_in_channels=1,
        audio_out_channels=OUTPUT_CHANNELS,
        input_device=device,
        output_device=device,
        playback_gain_db=PLAYBACK_GAIN_DB,
    ))

    stt = DeepgramSTTService(
        api_key=settings.deepgram_api_key,
        sample_rate=INPUT_SAMPLE_RATE,
        settings=DeepgramSTTService.Settings(
            model="nova-3-general",
            language="en-US",
            smart_format=True,
            interim_results=True,
        ),
    )

    tts = ElevenLabsTTSService(
        api_key=settings.elabs_api_key,
        sample_rate=OUTPUT_SAMPLE_RATE,
        settings=ElevenLabsTTSService.Settings(
            voice=settings.elabs_voice_id,
            model="eleven_turbo_v2_5",   # ~75-150ms TTFA vs ~400ms for multilingual_v2
            language="en",
            stability=0.55,
            similarity_boost=1.0,
            speed=1.08,
        ),
    )

    llm = AnthropicLLMService(
        api_key=settings.anthropic_api_key,
        settings=AnthropicLLMService.Settings(
            model="claude-haiku-4-5",
            system_instruction=await _build_claudia_system_prompt(),
            max_tokens=512,
            enable_prompt_caching=True,
        ),
    )

    _register_tools(llm, SHARED_TOOLS)

    context = LLMContext(
        tools=ToolsSchema(standard_tools=[_to_pipecat_schema(t) for t in SHARED_TOOLS]),
    )

    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(
                sample_rate=INPUT_SAMPLE_RATE,
                params=VADParams(
                    confidence=0.7,
                    start_secs=0.2,
                    stop_secs=0.2,
                    min_volume=0.35,
                ),
            ),
        ),
    )

    # Strip `<thinking>…</thinking>` scratchpad that Haiku occasionally emits
    # as literal text in its response (training artifact — not the structured
    # extended-thinking API feature we'd have to opt into). PatternPairAggregator
    # + LLMTextProcessor is pipecat's idiomatic extension point: the processor
    # turns LLMTextFrame → AggregatedTextFrame using our aggregator; TTS speaks
    # the clean chunks. See docs/references/pipecat/INDEX.md.
    thinking_stripper = LLMTextProcessor(
        text_aggregator=PatternPairAggregator().add_pattern(
            type="thinking",
            start_pattern="<thinking>",
            end_pattern="</thinking>",
            action=MatchAction.REMOVE,
        ),
    )

    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        thinking_stripper,
        tts,
        transport.output(),
        assistant_aggregator,
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=INPUT_SAMPLE_RATE,
            audio_out_sample_rate=OUTPUT_SAMPLE_RATE,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=SESSION_IDLE_TIMEOUT_S,
        observers=[FrameFlowObserver(conversation_id=CONVERSATION_ID.get())],
    )

    # Seed a greeting request so Claudia speaks first.
    context.add_message({
        "role": "developer",
        "content": "Greet the user warmly in one sentence — you just heard them say your wake word.",
    })
    await task.queue_frames([LLMRunFrame()])

    # handle_sigint=False — the voice channel installs its own SIGTERM/SIGINT
    # handler on the outer event loop; PipelineRunner's default SIGINT
    # handling would double-fire.
    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)
    return context


def _conversation_turns(context: LLMContext) -> list[dict]:
    """Extract spoken user/assistant turns from an LLMContext for the session log.

    Skips `system` / `developer` / `tool` roles — the session log captures
    what was actually spoken, not the instrumentation around it.
    """
    turns = []
    for msg in context.get_messages():
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            turns.append({"role": role, "text": content})
    return turns


async def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    missing = [f for f in ("deepgram_api_key", "anthropic_api_key", "elabs_api_key", "elabs_voice_id")
               if not getattr(settings, f)]
    if missing:
        sys.exit(f"Missing env vars in .env: {', '.join(m.upper() for m in missing)}")

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    # Without this, SIGTERM skips async unwind and leaves the portaudio thread
    # holding the Jabra ALSA capture handle, breaking the next startup.
    loop = asyncio.get_running_loop()
    main_task = asyncio.current_task()
    assert main_task is not None
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, main_task.cancel)

    jabra = find_jabra()
    logger.info(f"Jabra device index: {jabra} (pid={os.getpid()})")
    _log_event({"type": "channel_started", "device_index": jabra})

    try:
        while True:
            score = await wait_for_wake(jabra)
            # One ID per wake, threaded through: the voice session log, sub-agent
            # invocations (via the CONVERSATION_ID ContextVar), and
            # `conversation_end`. Lets `jq` join a voice turn to its ask_wiki
            # traces after the fact.
            conversation_id = str(uuid.uuid4())
            cid_token = CONVERSATION_ID.set(conversation_id)
            _log_event({
                "type": "wake",
                "score": round(score, 3),
                "conversation_id": conversation_id,
            })

            try:
                context = await run_conversation(jabra)
                _log_event({
                    "type": "conversation_end",
                    "reason": "idle",
                    "conversation_id": conversation_id,
                    "turns": _conversation_turns(context),
                })
            except Exception as e:
                logger.exception("conversation failed")
                _log_event({
                    "type": "conversation_end",
                    "reason": "error",
                    "conversation_id": conversation_id,
                    "error": str(e),
                })
            finally:
                CONVERSATION_ID.reset(cid_token)

            logger.info("← conversation ended, back to listening\n")
    except (KeyboardInterrupt, asyncio.CancelledError):
        _log_event({"type": "channel_stopped"})
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
