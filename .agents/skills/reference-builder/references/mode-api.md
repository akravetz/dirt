# Mode: api

Use when the concept is a hosted service with a focused surface area — a single endpoint, an SDK, or one specific feature of a provider. Examples: Deepgram TTS, Gemini 3.1 Live API, Stripe Terminal, Supabase Realtime, OpenAI Responses API.

## Strategy

Synthesize from official docs + SDK READMEs. The surface is small enough that a web-search + a handful of targeted fetches beats downloading a whole doc tree. No `raw/` directory.

The single biggest threat in API packs is **wire-format drift** — training data routinely hallucinates exact JSON field names, endpoint paths, and streaming message types. The pack must be airtight on those specifics.

## Step 1 — Locate authoritative sources

Search for:

1. Official API reference for this *specific* feature (not the whole provider — e.g. `deepgram.com/docs/text-to-speech` not `deepgram.com/docs`)
2. Provider's SDK README on GitHub — often has the most current working code
3. Recent provider blog posts announcing the feature or version
4. Official migration guide if one exists
5. Provider's OpenAPI spec or TypeScript SDK types if they're published

Prefer 3-6 authoritative URLs over 20 mediocre ones. The quality of sources matters more than quantity.

## Step 2 — Identify the topics

An API pack typically wants topic files covering:

- **Request / response format** — exact shape, required/optional fields, enums, constraints. This is the single most important topic in API mode because it's where training-data drift is worst.
- **Auth** — how to authenticate, where keys come from, token scopes, rate-limit handling
- **Quick-start** — minimal working example for the primary use case (TTS: text → audio bytes; STT: audio → transcript; LLM: prompt → completion; Realtime: open socket → subscribe → receive)
- **Streaming / WebSocket protocol** — if the API supports it, split this into its own topic. Streaming protocols change frequently between versions and are where agents most confidently hallucinate.
- **Error handling** — status codes, retry/backoff guidance, rate limit headers, idempotency
- **Common patterns** — batching, chunking, language/voice/model selection, cost optimization

Pick 3-6 topics. Don't over-split — a pack with 10 API topics is noise.

## Step 3 — Hardcode the wire format

Training data most often hallucinates:

- **Exact JSON field names** (`voice.name` vs `voice_name` vs `voiceId`)
- **Endpoint paths** (`/v1/generate` vs `/v1/tts` vs `/v1/speech`)
- **Streaming message types** (`delta` vs `chunk` vs `partial`)
- **Parameter enums** (model IDs, voice IDs, format strings)

For any topic file covering wire format: **copy the exact request/response shape from official docs, verbatim.** Do not paraphrase. Include at least one complete working curl example and at least one complete working SDK example, both cited.

**Example of tight wire-format writing:**

```markdown
## Request shape

POST `https://api.example.com/v3/speak`

Source: https://example.com/docs/api/v3/tts/speak

```json
{
  "text": "Hello world",
  "voice": {
    "name": "en-US-aurora",
    "speed": 1.0
  },
  "format": "mp3_44100"
}
```

`voice.name` is required. Valid values: `en-US-aurora`, `en-GB-atlas`, `ja-JP-koto` (full list: https://example.com/docs/voices).

### Common mistakes

Training data may suggest `voice_name` (v2 flat shape) or `voiceId` (never correct). Use nested `voice.name`.
```

## Step 4 — Write topic files and INDEX.md

Per [pack-structure.md](pack-structure.md). For api mode:

- INDEX.md's "When to consult this pack" should name the specific tasks: "when writing request bodies, handling responses, setting up streaming, or managing auth for <API>."
- The "Version-specific warnings" section can be omitted if this API has a single stable version; otherwise list the version and the most confusable old-vs-new differences.
- No `raw/` directory — api mode is synthesis, not mirror.

## Step 5 — Verify

- Every wire-format claim (field name, endpoint path, enum value) has a source URL next to it.
- The quick-start topic has a complete, runnable code example.
- If the API streams, the streaming topic has a full message-type table with example payloads.
- "Common mistakes" block on the wire-format topic listing at least 2-3 hallucination-prone defaults.
