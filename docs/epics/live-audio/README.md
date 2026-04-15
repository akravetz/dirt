# Epic: Live Audio (Mic + Speaker)

Status: planning
Priority: medium
Created: 2026-04-12

## Goal

Add an always-on microphone and speaker near the grow tent, enabling live voice communication with Claude. The user can speak naturally to give updates, ask questions, or request actions — and Claude can respond audibly.

## Hardware

| Component | Model | Specs |
|-----------|-------|-------|
| Speakerphone | Jabra Speak 410 | USB, omnidirectional mic, full-duplex, portable |
| Connection | USB-A | Via RSHTECH 10-port hub |

**Why Jabra Speak 410:**
- Single USB device handles both mic and speaker
- Omnidirectional mic with good pickup radius
- Designed for conference calls — handles background noise well
- Portable, sits on a desk/shelf near the tent (not inside — too humid)
- Shows up as standard USB audio device on Linux, no drivers needed

## Scope

### Audio Capture Service
- Continuous listening or wake-word/push-to-talk activation
- Audio stream capture from USB audio device
- Speech-to-text pipeline (Whisper or cloud STT)
- Noise handling for tent environment (fans, pumps)

### Voice Response
- Text-to-speech pipeline for Claude's responses
- Playback through Jabra speaker
- Volume control, interrupt handling

### Web UI Integration
- Mute/unmute toggle
- Volume control
- Audio activity indicator
- Transcript view (what was heard, what was said)

### MCP Integration
- MCP tool for Claude to send voice messages
- Audio input as an alternative to text input for Claude interactions

### Placement
- Jabra sits outside the tent near the monitoring host (not inside — humidity)
- Tent is in a bedroom closet, so audio path is short
- No bright LEDs to worry about during dark period (Jabra has a subtle ring light that can be covered)

## Considerations

- **Privacy** — mute controls are essential; Jabra has a physical mute button
- **Latency** — STT + Claude API + TTS pipeline needs to feel conversational (<3s round-trip ideal)
- **Dark period** — no light leaks from the device into the tent
- **Noise floor** — tent fans run 24/7; STT model needs to handle this

## Acceptance Criteria

- User can speak and have their words transcribed for Claude
- Claude can respond with synthesized speech through the Jabra speaker
- System handles ambient noise without significant degradation
- Mute/disable controls available via web UI and physical Jabra button
- Transcript of voice interactions logged to `sessions/voice/YYYY-MM-DD.jsonl`
- No light leaks into tent during dark period

## References

### Jabra Speak 410
- [Amazon product page (B007SHJIO2)](https://www.amazon.com/dp/B007SHJIO2) — USB corded speakerphone, omnidirectional mic, full-duplex

### Architecture
- [ADR 005: Agent Architecture](../../adrs/005-agent-architecture.md) — ephemeral agent loops, session logging, channel adapter pattern
- [OpenClaw Architecture (Substack)](https://ppaolo.substack.com/p/openclaw-system-architecture-overview) — reference architecture for multi-channel agent with voice

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:live-audio"`
