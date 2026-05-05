"""Tests for the pluggable transcript parser package."""

from __future__ import annotations

from pathlib import Path

import pytest

from cheap_llm import transcript
from cheap_llm.transcript import Message, Mode, Role, claude, codex, generic


FIX_DIR = Path(__file__).parent / "fixtures"
CLAUDE_FIXTURE = FIX_DIR / "sample_session_claude.jsonl"
CODEX_FIXTURE = FIX_DIR / "sample_session_codex.jsonl"


# --- format detection --------------------------------------------------------

def test_detect_format_claude_jsonl() -> None:
    parser = transcript.detect_format(CLAUDE_FIXTURE)
    assert parser is claude.parse


def test_detect_format_codex_jsonl() -> None:
    parser = transcript.detect_format(CODEX_FIXTURE)
    assert parser is codex.parse


def test_detect_format_unknown_falls_back_to_generic(tmp_path: Path) -> None:
    f = tmp_path / "weird.jsonl"
    f.write_text('{"foo": "bar"}\n', encoding="utf-8")
    parser = transcript.detect_format(f)
    assert parser is generic.parse


def test_detect_format_empty_file_falls_back_to_generic(tmp_path: Path) -> None:
    f = tmp_path / "empty.jsonl"
    f.write_text("", encoding="utf-8")
    parser = transcript.detect_format(f)
    assert parser is generic.parse


def test_detect_format_invalid_json_falls_back_to_generic(tmp_path: Path) -> None:
    f = tmp_path / "broken.jsonl"
    f.write_text("not json at all\n", encoding="utf-8")
    parser = transcript.detect_format(f)
    assert parser is generic.parse


# --- claude parser -----------------------------------------------------------

def test_claude_parser_yields_text_and_tool_messages() -> None:
    msgs = list(claude.parse(CLAUDE_FIXTURE))
    roles = [m.role for m in msgs]
    # Fixture has: summary(meta), user, assistant-text, tool_use,
    # tool_result, assistant-text, user, assistant-text.
    assert Role.META in roles
    assert roles.count(Role.USER) == 2
    assert roles.count(Role.ASSISTANT) == 3
    assert roles.count(Role.TOOL_USE) == 1
    assert roles.count(Role.TOOL_RESULT) == 1


def test_claude_parser_extracts_tool_name() -> None:
    msgs = list(claude.parse(CLAUDE_FIXTURE))
    tool_uses = [m for m in msgs if m.role == Role.TOOL_USE]
    assert len(tool_uses) == 1
    assert tool_uses[0].tool_name == "Read"
    assert "auth.py" in tool_uses[0].text  # input rendered as JSON


def test_claude_parser_skips_malformed_lines(tmp_path: Path) -> None:
    f = tmp_path / "partial.jsonl"
    f.write_text(
        '{"sessionId":"x","type":"user","message":{"role":"user","content":"hi"}}\n'
        'not valid json\n'
        '{"sessionId":"x","type":"assistant","message":{"role":"assistant","content":"yo"}}\n',
        encoding="utf-8",
    )
    msgs = list(claude.parse(f))
    # Two valid lines → at most two messages (one per turn), no crash.
    assert len(msgs) == 2
    assert msgs[0].role == Role.USER
    assert msgs[1].role == Role.ASSISTANT


# --- codex parser ------------------------------------------------------------

def test_codex_parser_handles_session_meta_response_item_event_msg() -> None:
    msgs = list(codex.parse(CODEX_FIXTURE))
    roles = [m.role for m in msgs]
    # session_meta(meta), event_msg UserMessage(user), response_item assistant text(asst),
    # response_item function_call(tool_use), event_msg ItemCompleted(tool_result),
    # response_item assistant text(asst), event_msg UserMessage(user),
    # response_item assistant text(asst), event_msg TokenCount(meta).
    assert Role.META in roles
    assert roles.count(Role.USER) == 2
    assert roles.count(Role.ASSISTANT) == 3
    assert roles.count(Role.TOOL_USE) == 1
    assert roles.count(Role.TOOL_RESULT) == 1


def test_codex_parser_extracts_function_call_name() -> None:
    msgs = list(codex.parse(CODEX_FIXTURE))
    tool_uses = [m for m in msgs if m.role == Role.TOOL_USE]
    assert len(tool_uses) == 1
    assert tool_uses[0].tool_name == "shell"
    assert "auth.py" in tool_uses[0].text


# --- generic parser ----------------------------------------------------------

def test_generic_parser_returns_one_other_blob(tmp_path: Path) -> None:
    f = tmp_path / "anything.txt"
    f.write_text("hello world\n", encoding="utf-8")
    msgs = list(generic.parse(f))
    assert len(msgs) == 1
    assert msgs[0].role == Role.OTHER
    assert "hello world" in msgs[0].text


# --- mode filters and tail ---------------------------------------------------

def test_filter_mode_full_passes_through() -> None:
    msgs = list(claude.parse(CLAUDE_FIXTURE))
    out = list(transcript.filter_mode(iter(msgs), Mode.FULL))
    assert out == msgs


def test_filter_mode_messages_only_drops_tool_events_and_meta() -> None:
    msgs = list(claude.parse(CLAUDE_FIXTURE))
    out = list(transcript.filter_mode(iter(msgs), Mode.MESSAGES_ONLY))
    # Strict invariant: messages-only keeps ONLY user + assistant turns.
    # Tool events, META (session_meta/summary), generic OTHER all drop.
    assert all(m.role in (Role.USER, Role.ASSISTANT) for m in out)
    # Sanity: user/assistant turns remain (5 of them in the fixture).
    assert len(out) == 5


def test_filter_mode_messages_only_drops_meta_from_codex() -> None:
    """Codex fixture has session_meta + TokenCount (META). messages-only must drop them."""
    msgs = list(codex.parse(CODEX_FIXTURE))
    assert any(m.role == Role.META for m in msgs)  # precondition
    out = list(transcript.filter_mode(iter(msgs), Mode.MESSAGES_ONLY))
    assert all(m.role in (Role.USER, Role.ASSISTANT) for m in out)


def test_take_tail_returns_last_n() -> None:
    msgs = list(claude.parse(CLAUDE_FIXTURE))
    last3 = transcript.take_tail(msgs, 3)
    assert last3 == msgs[-3:]


def test_take_tail_none_returns_all() -> None:
    msgs = list(claude.parse(CLAUDE_FIXTURE))
    assert transcript.take_tail(msgs, None) == msgs


def test_take_tail_zero_returns_all() -> None:
    msgs = list(claude.parse(CLAUDE_FIXTURE))
    assert transcript.take_tail(msgs, 0) == msgs


# --- prompt rendering --------------------------------------------------------

def test_render_for_prompt_uses_role_tags() -> None:
    msgs = [
        Message(role=Role.USER, text="hi"),
        Message(role=Role.ASSISTANT, text="hello"),
        Message(role=Role.TOOL_USE, text='{"file":"x"}', tool_name="Read"),
    ]
    rendered = transcript.render_for_prompt(msgs)
    assert "[USER] hi" in rendered
    assert "[ASSISTANT] hello" in rendered
    assert "[TOOL_USE: Read]" in rendered


def test_render_for_prompt_skips_empty_text_for_chat_roles() -> None:
    msgs = [
        Message(role=Role.USER, text="   "),
        Message(role=Role.ASSISTANT, text="content"),
    ]
    rendered = transcript.render_for_prompt(msgs)
    assert "[USER]" not in rendered
    assert "[ASSISTANT] content" in rendered
