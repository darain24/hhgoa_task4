import pytest
from tracework import store


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", tmp_path / "test.db")
    store.init()
    with store.connect() as c:
        c.executescript(
            "CREATE TABLE transactions(id TEXT PRIMARY KEY,amount REAL,card_id TEXT,card_verified INTEGER); CREATE TABLE history(id TEXT PRIMARY KEY);"
        )
        c.execute("INSERT INTO transactions VALUES(?,?,?,?)", ("t1", 125, "c1", 1))
    return tmp_path
