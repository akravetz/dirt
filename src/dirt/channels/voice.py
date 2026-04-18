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
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sounddevice as sd
from loguru import logger
from openwakeword.model import Model

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
from pipecat.adapters.schemas.tools_schema import FunctionSchema, ToolsSchema
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

from dirt.channels._audio_transport import (
    SoundDeviceTransport,
    SoundDeviceTransportParams,
)
from dirt.config import settings
from dirt.tools import SHARED_TOOLS, ToolSpec

ROOT = Path(__file__).resolve().parents[3]

# Written on startup, unlinked on clean shutdown. `kill $(cat logs/voice.pid)`
# always targets the actual Python PID — no pattern-matching, no uv wrapper
# confusion, no risk of pkill matching its own shell.
PID_FILE = ROOT / "logs" / "voice.pid"

# Wake model — trained on user-voice ElevenLabs clones + captured RIRs.
# See wiki/decisions/2026-04-16-wake-word-training-strategy.md.
WAKE_MODEL_PATH = ROOT / "debug" / "hey_claudia.onnx"
WAKE_SAMPLE_RATE = 16000
WAKE_CHUNK_SAMPLES = int(WAKE_SAMPLE_RATE * 0.08)   # 80 ms
WAKE_THRESHOLD = 0.35
WAKE_DEBOUNCE_S = 3.0
WAKE_WARMUP_FRAMES = 12   # ~1s at 80ms/frame — drop post-conversation echo tail

# Jabra SPEAK 410 hardware constraints
INPUT_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 48000     # firmware clock
OUTPUT_CHANNELS = 2            # stereo-only playback endpoint
PLAYBACK_GAIN_DB = 12.0

SESSION_IDLE_TIMEOUT_S = 15

SESSIONS_DIR = ROOT / "sessions" / "voice"

CLAUDIA_SYSTEM_PROMPT = (
    "Your name is Claudia. You are a warm, confident, sassy 28-year-old "
    "Colombian woman who speaks with natural charm and a little playful "
    "flirtation. You mix the occasional Spanish expression into English "
    "('ay', 'querido', 'de verdad', 'mi amor') but the conversation is "
    "mostly English. You are speaking aloud in a real-time voice "
    "conversation, so: no emojis, no bullet points, no markdown — just "
    "natural spoken sentences. Keep replies short (one or two sentences) "
    "unless asked for more. Don't over-apologize; be direct and a little "
    "bit cheeky.\n\n"
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _session_log_path() -> Path:
    return SESSIONS_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"


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
        while True:
            frame = await q.get()
            score = model.predict(frame)[model_name]
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
                return float(score)


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
            system_instruction=CLAUDIA_SYSTEM_PROMPT,
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

    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
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
    logger.add(sys.stderr, level="INFO")

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
            _log_event({"type": "wake", "score": round(score, 3)})

            try:
                context = await run_conversation(jabra)
                _log_event({
                    "type": "conversation_end",
                    "reason": "idle",
                    "turns": _conversation_turns(context),
                })
            except Exception as e:
                logger.exception("conversation failed")
                _log_event({"type": "conversation_end", "reason": "error", "error": str(e)})

            logger.info("← conversation ended, back to listening\n")
    except (KeyboardInterrupt, asyncio.CancelledError):
        _log_event({"type": "channel_stopped"})
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
