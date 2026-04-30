from __future__ import annotations

from datetime import date

from dirt_shared.services.daily_synthesis import (
    CodexSynthesisRunner,
    _extract_codex_usage,
    _last_codex_message,
    _parse_jsonl_events,
)


def test_codex_runner_builds_exec_command_with_images(tmp_path):
    runner = CodexSynthesisRunner(
        repo_root=tmp_path,
        wiki_root=tmp_path / "wiki",
        log_dir=tmp_path / "logs",
        codex_bin="/usr/local/bin/codex",
        model="gpt-5.5",
        sandbox="workspace-write",
    )
    photos = [tmp_path / "a.jpg", tmp_path / "b.jpg"]

    cmd = runner._build_command(date(2026, 4, 29), photos)

    assert cmd[:3] == ["/usr/local/bin/codex", "exec", "--json"]
    assert "-C" in cmd
    assert str(tmp_path) in cmd
    assert "--model" in cmd
    assert "gpt-5.5" in cmd
    assert cmd.count("--image") == 2
    assert cmd[-1] == "-"


def test_parse_jsonl_events_preserves_unparsed_lines():
    events = _parse_jsonl_events(
        '{"type":"agent_message","message":"done"}\nnot json\n'
    )

    assert events == [
        {"type": "agent_message", "message": "done"},
        {"type": "unparsed_stdout", "text": "not json"},
    ]


def test_last_codex_message_prefers_trailing_text():
    events = [
        {"type": "agent_message", "message": "first"},
        {"type": "item", "item": {"content": [{"text": "last"}]}},
    ]

    assert _last_codex_message(events) == "last"


def test_extract_codex_usage_returns_last_usage():
    events = [
        {"type": "turn", "usage": {"input_tokens": 10}},
        {"type": "turn", "usage": {"input_tokens": 20}},
    ]

    assert _extract_codex_usage(events) == {"input_tokens": 20}
