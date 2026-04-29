"""Store tests (SQLite only unless CONVAIX_TEST_PG_URL is set)."""
from convaix.schema import convert_to_schema, add_convaix_extension


def _sample_conv(source="claude", idx=1):
    c = convert_to_schema(source, f"id-{idx}", f"Test {idx}",
                          [{"role": "user", "content": "Tell me about embeddings and vector search"},
                           {"role": "assistant", "content": "Embeddings are numerical representations of text used for semantic similarity search."}])
    add_convaix_extension(c, "test")
    return c


def test_load_and_list(sqlite_store):
    conv = _sample_conv()
    assert sqlite_store.load_snapshot(conv) is True
    assert sqlite_store.load_snapshot(conv) is False  # duplicate
    rows = sqlite_store.list_snapshots()
    assert len(rows) == 1
    assert rows[0]["source"] == "claude"


def test_chunk_snapshot(sqlite_store):
    conv = _sample_conv()
    sqlite_store.load_snapshot(conv)
    n = sqlite_store.chunk_snapshot(conv, skip_embeddings=True)
    assert n > 0


def test_search_keyword(sqlite_store):
    conv = _sample_conv()
    sqlite_store.load_snapshot(conv)
    sqlite_store.chunk_snapshot(conv, skip_embeddings=True)
    results = sqlite_store.search_chunks("embeddings", mode="keyword")
    assert len(results) > 0


def test_search_conversations(sqlite_store):
    conv = _sample_conv()
    sqlite_store.load_snapshot(conv)
    sqlite_store.chunk_snapshot(conv, skip_embeddings=True)
    results = sqlite_store.search_conversations("embeddings")
    assert len(results) > 0


def test_discussion(sqlite_store):
    did = sqlite_store.create_discussion("Test chat", "nitin")
    sqlite_store.add_discussion_message(did, "nitin", "Hello")
    sqlite_store.add_discussion_message(did, "assistant", "Hi!")
    msgs = sqlite_store.get_discussion_messages(did)
    assert len(msgs) == 2
