from __future__ import annotations

from workspace_ai.workspace_memory.session_store import SessionStore


def test_session_store_crud_and_checkpoint(isolated_workspace_env):
    store = SessionStore(db_path=str(isolated_workspace_env))

    session = store.create_session(project_id="workspace", title="Test session", mode="chat")
    assert session["project_id"] == "workspace"

    message = store.add_message(session_id=session["session_id"], role="user", content="hello")
    assert message["content"] == "hello"

    checkpoint = store.create_checkpoint(session_id=session["session_id"], summary="snap", state={"step": 1})
    assert checkpoint["summary"] == "snap"

    listed = store.list_sessions(project_id="workspace")
    assert len(listed) == 1

    assert store.delete_session(session_id=session["session_id"]) is True
    assert store.get_session(session["session_id"]) is None
