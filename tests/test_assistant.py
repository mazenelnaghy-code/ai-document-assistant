import json
import sys
from pathlib import Path

import anthropic
import httpx2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import assistant  # noqa: E402
import make_sample_docs  # noqa: E402


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    folder = tmp_path_factory.mktemp("docs")
    make_sample_docs.main(folder)
    return assistant.load_pages(folder)


def fake_client(response_json, seen):
    """The real SDK, talking to a fake API that records the request and returns `response_json`."""
    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["headers"] = request.headers
        return httpx2.Response(200, json=response_json)
    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    return anthropic.Anthropic(api_key="test-key", http_client=http, max_retries=0)


def message(content, stop_reason="end_turn"):
    return {"id": "msg_test", "type": "message", "role": "assistant", "model": assistant.MODEL,
            "content": content, "stop_reason": stop_reason, "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 60}}


def test_every_page_is_loaded(pages):
    assert len(pages) == 14
    assert {p.file for p in pages} == {"employee_handbook.pdf", "refund_policy.pdf", "it_security_policy.pdf"}


@pytest.mark.parametrize("question, expected", [
    ("How many days of annual leave do I get?", "employee_handbook.pdf, page 2"),
    ("Can I return opened electronics?", "refund_policy.pdf, page 1"),
    ("How long do card refunds take?", "refund_policy.pdf, page 2"),
    ("What is the meal allowance when travelling?", "employee_handbook.pdf, page 5"),
    ("What should I do if I lose my laptop?", "it_security_policy.pdf, page 2"),
])
def test_search_finds_the_right_page_first(pages, question, expected):
    assert assistant.search(pages, question)[0].title == expected


def test_search_returns_nothing_for_unrelated_questions(pages):
    assert assistant.search(pages, "zebra quantum") == []


def test_stem():
    assert [assistant.stem(w) for w in ("meals", "travelling", "returned", "glass")] == ["meal", "travel", "return", "glass"]


def test_request_sends_only_the_matching_pages_with_citations(pages):
    hits = assistant.search(pages, "Can I work from home?", k=2)
    seen = {}
    client = fake_client(message([{"type": "text", "text": "Yes.", "citations": None}]), seen)
    assistant.ask(client, "Can I work from home?", hits)

    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    content = body["messages"][0]["content"]
    assert [c["type"] for c in content] == ["document", "document", "text"]
    assert all(c["citations"] == {"enabled": True} for c in content[:2])
    assert content[0]["title"] == hits[0].title
    assert content[-1]["text"] == "Can I work from home?"


def test_answer_is_numbered_with_its_sources(pages):
    hits = assistant.search(pages, "How many days of annual leave do I get?")
    title = hits[0].title
    quote = "Full-time employees receive 21 working days of paid annual leave per year."
    response = message([
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "text", "text": "You get ", "citations": None},
        {"type": "text", "text": "21 working days of paid leave a year", "citations": [{
            "type": "char_location", "cited_text": quote, "document_index": 0, "document_title": title,
            "start_char_index": 0, "end_char_index": len(quote)}]},
        {"type": "text", "text": ".", "citations": None},
    ])
    answer = assistant.ask(fake_client(response, {}), "How many days of annual leave do I get?", hits)
    assert answer.text == "You get 21 working days of paid leave a year [1]."
    assert answer.sources == [(title, quote)]
    assert f'[1] {title}: "{quote}"' in assistant.format_answer(answer)


def test_refusal_is_reported_not_printed_as_an_answer(pages):
    hits = assistant.search(pages, "How long do card refunds take?")
    response = message([], stop_reason="refusal")
    answer = assistant.ask(fake_client(response, {}), "How long do card refunds take?", hits)
    assert answer.refused and answer.sources == []


def test_no_matching_pages_means_no_api_call():
    class NoCalls:
        beta = None  # any attribute access on .beta.messages would raise
    answer = assistant.ask(NoCalls(), "zebra quantum", [])
    assert answer.text == "None of the documents mention that."
