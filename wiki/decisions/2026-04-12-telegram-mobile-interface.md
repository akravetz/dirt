---
title: "Mobile Chat Interface: Telegram Bot"
type: decision
sources: []
related: []
created: 2026-04-12
updated: 2026-04-12
---

# Decision: Mobile Chat Interface — Telegram Bot

**Date:** 2026-04-12
**Status:** Accepted

## Context

Need a mobile-accessible chat interface for the user to interact with Claude about the grow on the go — ask questions, get status updates, receive proactive alerts (VPD out of range, soil moisture low), and view camera snapshots. Similar to how OpenClaw uses WhatsApp integrations.

## Decision

**Telegram bot** using `python-telegram-bot` library, integrated into the dirt FastAPI app.

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| WhatsApp (Twilio/Meta API) | Most popular messenger | Meta Business account required, Twilio costs, message template approval for proactive sends, webhook SSL ceremony |
| SMS (Twilio) | Universal, no app needed | No rich messages (photos, markdown, buttons), per-message cost |
| Custom PWA | Full control, lives in dirt web app | Building a chat UI from scratch, notification reliability on mobile |
| Discord bot | Easy bot setup, rich messages | Overkill for 1:1, gaming-platform feel |
| Slack | Good bot ecosystem | Not a personal mobile messenger |

## Rationale

- **Lowest friction setup:** Create bot via BotFather in 30 seconds, get token, write handler
- **No business verification** or approval processes
- **Rich messages:** Markdown, inline photos (camera snapshots), buttons, formatted tables
- **Proactive messaging works natively** — push alerts without user initiating
- **python-telegram-bot** is mature, async, fits directly into existing FastAPI app
- **Free** for personal use, no per-message costs
- Telegram mobile app is polished and likely already installed
- Bot restricted to single authorized user ID for security
