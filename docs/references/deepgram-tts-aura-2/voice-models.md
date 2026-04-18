---
title: Deepgram TTS voice models
concept: deepgram-tts-aura-2
updated: 2026-04-17
source: https://developers.deepgram.com/docs/tts-models
---

> This file anchors agents to current Deepgram voice-model identifiers. Prefer what's listed here over recollection — model lists are particularly hallucination-prone.

# Voice models

## Naming convention

```
aura-<generation>-<voice_name>-<language_code>
```

- Generation: `aura` (Aura-1, legacy) or `aura-2` (current).
- `voice_name`: e.g. `thalia`, `zeus`, `asteria`.
- `language_code`: ISO-639-1 (`en`, `es`, `fr`, `de`, `it`, `ja`, `nl`).

Example: `aura-2-thalia-en`, `aura-2-ebisu-ja`, `aura-hera-en` (Aura-1).

The value appears in the **query string** (`?model=aura-2-thalia-en`) for REST and WebSocket connections, and as the `model` option on SDK call-sites. It never goes in the JSON body. It is never called `voice`, `voice_id`, or `voice_name`.

## Current generation: Aura-2

Source: https://developers.deepgram.com/docs/tts-models

### English (40 voices)
`aura-2-amalthea-en`, `aura-2-andromeda-en`, `aura-2-apollo-en`, `aura-2-arcas-en`, `aura-2-aries-en`, `aura-2-asteria-en`, `aura-2-athena-en`, `aura-2-atlas-en`, `aura-2-aurora-en`, `aura-2-callista-en`, `aura-2-cora-en`, `aura-2-cordelia-en`, `aura-2-delia-en`, `aura-2-draco-en`, `aura-2-electra-en`, `aura-2-harmonia-en`, `aura-2-helena-en`, `aura-2-hera-en`, `aura-2-hermes-en`, `aura-2-hyperion-en`, `aura-2-iris-en`, `aura-2-janus-en`, `aura-2-juno-en`, `aura-2-jupiter-en`, `aura-2-luna-en`, `aura-2-mars-en`, `aura-2-minerva-en`, `aura-2-neptune-en`, `aura-2-odysseus-en`, `aura-2-ophelia-en`, `aura-2-orion-en`, `aura-2-orpheus-en`, `aura-2-pandora-en`, `aura-2-phoebe-en`, `aura-2-pluto-en`, `aura-2-saturn-en`, `aura-2-selene-en`, `aura-2-thalia-en`, `aura-2-theia-en`, `aura-2-vesta-en`, `aura-2-zeus-en`

### Spanish (17)
`aura-2-agustina-es`, `aura-2-alvaro-es`, `aura-2-antonia-es`, `aura-2-aquila-es`, `aura-2-carina-es`, `aura-2-celeste-es`, `aura-2-diana-es`, `aura-2-estrella-es`, `aura-2-gloria-es`, `aura-2-javier-es`, `aura-2-luciano-es`, `aura-2-nestor-es`, `aura-2-olivia-es`, `aura-2-selena-es`, `aura-2-silvia-es`, `aura-2-sirio-es`, `aura-2-valerio-es`

### Dutch (9)
`aura-2-beatrix-nl`, `aura-2-cornelia-nl`, `aura-2-daphne-nl`, `aura-2-hestia-nl`, `aura-2-leda-nl`, `aura-2-lars-nl`, `aura-2-rhea-nl`, `aura-2-roman-nl`, `aura-2-sander-nl`

### French (2)
`aura-2-agathe-fr`, `aura-2-hector-fr`

### German (7)
`aura-2-aurelia-de`, `aura-2-elara-de`, `aura-2-fabian-de`, `aura-2-julius-de`, `aura-2-kara-de`, `aura-2-lara-de`, `aura-2-viktoria-de`

### Italian (10)
`aura-2-cesare-it`, `aura-2-cinzia-it`, `aura-2-demetra-it`, `aura-2-dionisio-it`, `aura-2-elio-it`, `aura-2-flavio-it`, `aura-2-livia-it`, `aura-2-maia-it`, `aura-2-melia-it`, `aura-2-perseo-it`

### Japanese (5)
`aura-2-ama-ja`, `aura-2-ebisu-ja`, `aura-2-fujin-ja`, `aura-2-izanami-ja`, `aura-2-uzume-ja`

## Legacy: Aura-1 (still served)

`aura-angus-en`, `aura-arcas-en`, `aura-asteria-en`, `aura-athena-en`, `aura-helios-en`, `aura-hera-en`, `aura-luna-en`, `aura-orpheus-en`, `aura-orion-en`, `aura-perseus-en`, `aura-stella-en`, `aura-zeus-en`

Aura-1 is still accepted but Aura-2 is the current generation and should be preferred for new integrations. Training data will often default to `aura-asteria-en` (Aura-1) — pick an Aura-2 voice unless there is a specific reason to pin Aura-1.

## Picking a voice

- For English agents, `aura-2-thalia-en` and `aura-2-asteria-en` are the common defaults cited in Deepgram's own docs.
- For Spanish agents, `aura-2-estrella-es` and `aura-2-javier-es` are typical picks.
- Model id is end-to-end — the same id works for both REST and WebSocket.

## Common mistakes

- Using `voice_id` or `voice.name` as the field name — see [wire-format-rest.md](wire-format-rest.md). The field is always `model`, and it's a query parameter.
- Using `aura-2-thalia` (missing language suffix) — the language code is mandatory.
- Using `aura2-thalia-en` (no hyphen between `aura` and `2`) — the generation segment is `aura-2`.
- Expecting a `voices.list()` endpoint — voices are an enum documented at https://developers.deepgram.com/docs/tts-models, not a runtime-queried catalog.
