import pytest
from convaix.validate import validate_conversation, ValidationError
from convaix.schema import convert_to_schema, add_convaix_extension


def _make():
    c = convert_to_schema("claude", "id1", "Title", [{"role": "user", "content": "Hello"}])
    add_convaix_extension(c, "test")
    return c


def test_valid():
    validate_conversation(_make())


def test_missing_field():
    c = _make()
    del c["turns"]
    with pytest.raises(ValidationError):
        validate_conversation(c)


def test_bad_role():
    c = _make()
    c["turns"][0]["role"] = "robot"
    with pytest.raises(ValidationError):
        validate_conversation(c)
