import pytest
from tracework import engine, store


@pytest.fixture(autouse=True)
def offline_graph(monkeypatch):
    """No test may touch a real TigerGraph workspace.

    `engine.investigate` and `engine.respond` persist the case whenever TG_URL is
    configured, so without this the suite writes its fixture cases into whatever
    graph the developer happens to have connected. Tests that exercise the adapter
    patch it explicitly instead.
    """
    monkeypatch.setattr(engine, "TG_URL", "")


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
