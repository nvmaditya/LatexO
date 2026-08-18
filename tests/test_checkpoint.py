import sqlite3
from pathlib import Path

from latexo.checkpoint import load_checkpoint, save_checkpoints


def test_checkpoint_roundtrip_and_transaction(tmp_path: Path) -> None:
    store = tmp_path / "ckpt.sqlite"
    save_checkpoints(
        store,
        [
            {
                "thread_id": "t1",
                "revision_id": "rev-aaa",
                "patch_id": "p1",
                "payload": {"approval": True},
            }
        ],
    )
    loaded = load_checkpoint(store, "t1")
    assert loaded is not None
    assert loaded["revision_id"] == "rev-aaa"
    assert loaded["patch_id"] == "p1"
    assert loaded["payload"]["approval"] is True

    before = load_checkpoint(store, "t1")
    try:
        save_checkpoints(
            store,
            [
                {
                    "thread_id": "t2",
                    "revision_id": "rev-bbb",
                    "patch_id": "p2",
                    "payload": {},
                },
                {"thread_id": "t3"},
            ],
        )
    except Exception:
        pass
    assert load_checkpoint(store, "t2") is None
    assert load_checkpoint(store, "t1") == before
