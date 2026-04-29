"""Provider parser tests against fixture files."""
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def _validate_all(convs):
    from convaix.validate import validate_conversation
    for c in convs:
        validate_conversation(c)
    return convs


def test_claude_detect():
    from convaix.providers.claude import ClaudeParser
    p = ClaudeParser()
    assert p.detect(FIXTURES / "claude_sample.json")
    assert not p.detect(FIXTURES / "chatgpt_sample.json")


def test_claude_parse():
    from convaix.providers.claude import ClaudeParser
    convs = list(ClaudeParser().parse(FIXTURES / "claude_sample.json"))
    assert len(convs) == 1
    _validate_all(convs)
    assert convs[0]["conversation"]["source"] == "claude"
    assert convs[0]["statistics"]["turn_count"] == 4


def test_chatgpt_detect():
    from convaix.providers.chatgpt import ChatGPTParser
    p = ChatGPTParser()
    assert p.detect(FIXTURES / "chatgpt_sample.json")
    assert not p.detect(FIXTURES / "claude_sample.json")


def test_chatgpt_parse():
    from convaix.providers.chatgpt import ChatGPTParser
    convs = list(ChatGPTParser().parse(FIXTURES / "chatgpt_sample.json"))
    assert len(convs) == 1
    _validate_all(convs)
    assert convs[0]["conversation"]["source"] == "chatgpt"
    assert convs[0]["statistics"]["turn_count"] >= 2


def test_gemini_parse():
    from convaix.providers.gemini import GeminiParser
    convs = list(GeminiParser().parse(FIXTURES / "gemini_sample.json"))
    assert len(convs) >= 1
    _validate_all(convs)
    assert convs[0]["conversation"]["source"] == "gemini"


def test_auto_detect_claude():
    from convaix.providers import detect_parser
    p = detect_parser(FIXTURES / "claude_sample.json")
    assert p is not None
    assert p.name == "claude"
