"""Chat-session reads must be strongly consistent.

The chat page re-lists sessions right after a reply is saved, and
append_and_save loads-then-puts the whole session; an eventually consistent
read there drops the newest message.
"""

from backend.services.storage.dynamodb import DynamoDBStorageBackend


class _FakeTable:
    def __init__(self, pages, item=None):
        self.pages = pages
        self.item = item
        self.query_calls = []
        self.get_calls = []

    def query(self, **kwargs):
        self.query_calls.append(kwargs)
        return self.pages[len(self.query_calls) - 1]

    def get_item(self, **kwargs):
        self.get_calls.append(kwargs)
        return {"Item": self.item} if self.item else {}


def _backend(table):
    backend = DynamoDBStorageBackend.__new__(DynamoDBStorageBackend)
    backend.table = table
    return backend


def _item(session_id, updated_at):
    return {
        "session_id": session_id,
        "title": session_id,
        "messages": [{"role": "user", "content": "hi"}],
        "created_at": updated_at,
        "updated_at": updated_at,
    }


def test_list_chat_sessions_is_consistent_and_paginates():
    table = _FakeTable([
        {"Items": [_item("a", "2026-01-01T00:00:00+00:00")], "LastEvaluatedKey": {"k": 1}},
        {"Items": [_item("b", "2026-01-02T00:00:00+00:00")], "LastEvaluatedKey": {}},
    ])
    sessions = _backend(table).list_chat_sessions("alice")

    assert [s.id for s in sessions] == ["b", "a"]
    assert all(call["ConsistentRead"] for call in table.query_calls)
    assert table.query_calls[1]["ExclusiveStartKey"] == {"k": 1}


def test_load_chat_session_is_consistent():
    table = _FakeTable([], item=_item("a", "2026-01-01T00:00:00+00:00"))
    session = _backend(table).load_chat_session("alice", "a")

    assert session is not None and session.id == "a"
    assert table.get_calls[0]["ConsistentRead"] is True
