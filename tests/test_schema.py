from convaix.schema import convert_to_schema, add_convaix_extension, generate_conv_id, slugify


def test_slugify():
    assert slugify("Hello World!") == "hello-world"


def test_conv_id_stable():
    assert generate_conv_id("claude", "abc") == generate_conv_id("claude", "abc")


def test_convert_basic():
    turns = [{"role": "human", "content": "Hi"}, {"role": "model", "content": "Hello"}]
    r = convert_to_schema("gemini", "test-1", "Test", turns)
    assert r["schema_version"] == "1.0"
    assert r["turns"][0]["role"] == "user"
    assert r["turns"][1]["role"] == "assistant"
    assert r["statistics"]["turn_count"] == 2


def test_add_extension():
    conv = convert_to_schema("claude", "x1", "T", [{"role": "user", "content": "hi"}])
    add_convaix_extension(conv, "nitin")
    assert "x-convaix" in conv
    assert conv["x-convaix"]["convaix_id"].startswith("cx_")
