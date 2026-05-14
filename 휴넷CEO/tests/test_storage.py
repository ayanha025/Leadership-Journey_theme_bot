import os
import pytest
from storage import load_confirmed, append_confirmed


@pytest.fixture
def json_path(tmp_path):
    p = tmp_path / "confirmed.json"
    p.write_text("[]")
    return str(p)


def test_load_confirmed_empty(json_path):
    assert load_confirmed(json_path) == []


def test_append_and_load(json_path):
    append_confirmed({"keyword": "초격차", "category": "경영", "type": "article"}, json_path)
    result = load_confirmed(json_path)
    assert len(result) == 1
    assert result[0]["keyword"] == "초격차"
    assert "confirmed_at" in result[0]


def test_append_multiple(json_path):
    append_confirmed({"keyword": "A"}, json_path)
    append_confirmed({"keyword": "B"}, json_path)
    assert len(load_confirmed(json_path)) == 2


def test_load_creates_file_if_missing(tmp_path):
    path = str(tmp_path / "new.json")
    assert load_confirmed(path) == []
    assert os.path.exists(path)
