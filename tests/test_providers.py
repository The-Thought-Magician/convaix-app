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


def test_gemini_detect():
    from convaix.providers.gemini import GeminiParser
    p = GeminiParser()
    assert p.detect(FIXTURES / "gemini_sample.json")
    assert not p.detect(FIXTURES / "claude_sample.json")
    assert not p.detect(FIXTURES / "chatgpt_sample.json")


def test_auto_detect_claude():
    from convaix.providers import detect_parser
    p = detect_parser(FIXTURES / "claude_sample.json")
    assert p is not None
    assert p.name == "claude"


def test_auto_detect_chatgpt():
    from convaix.providers import detect_parser
    p = detect_parser(FIXTURES / "chatgpt_sample.json")
    assert p is not None
    assert p.name == "chatgpt"


def test_auto_detect_gemini():
    from convaix.providers import detect_parser
    p = detect_parser(FIXTURES / "gemini_sample.json")
    assert p is not None
    assert p.name == "gemini"


def test_chatgpt_does_not_detect_claude():
    from convaix.providers.chatgpt import ChatGPTParser
    p = ChatGPTParser()
    assert not p.detect(FIXTURES / "claude_sample.json")
    assert not p.detect(FIXTURES / "gemini_sample.json")


def test_idempotency():
    from convaix.providers.claude import ClaudeParser
    from convaix.schema import add_convaix_extension
    parser = ClaudeParser()
    convs1 = list(parser.parse(FIXTURES / "claude_sample.json"))
    convs2 = list(parser.parse(FIXTURES / "claude_sample.json"))
    assert len(convs1) == len(convs2)
    for c1, c2 in zip(convs1, convs2):
        # conv_id is deterministic (hash of source+source_id); convaix_id is UUID so compare conv_id
        assert c1["conversation"]["id"] == c2["conversation"]["id"]


def test_gemini_parse_turns():
    from convaix.providers.gemini import GeminiParser
    convs = list(GeminiParser().parse(FIXTURES / "gemini_sample.json"))
    assert len(convs) >= 1
    # Each conversation should have at least one turn
    for conv in convs:
        assert len(conv.get("turns", [])) >= 1
