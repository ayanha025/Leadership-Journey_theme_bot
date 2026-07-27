"""storage.py 공용 JSON I/O 유틸 테스트"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storage


def test_save_and_load_roundtrip(tmp_path):
    p = str(tmp_path / "sub" / "data.json")
    storage.save_json(p, {"a": 1, "b": ["x"]})
    assert storage.load_json(p, None) == {"a": 1, "b": ["x"]}


def test_load_missing_returns_default(tmp_path):
    p = str(tmp_path / "nope.json")
    assert storage.load_json(p, []) == []


def test_load_corrupt_returns_default(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert storage.load_json(str(p), {"d": True}) == {"d": True}


def test_save_creates_parent_dirs(tmp_path):
    p = tmp_path / "a" / "b" / "c.json"
    storage.save_json(str(p), [1, 2, 3])
    assert p.exists()


def test_roundtrip_preserves_unicode(tmp_path):
    p = str(tmp_path / "u.json")
    storage.save_json(p, ["한글", "테마"])
    assert storage.load_json(p, None) == ["한글", "테마"]


def test_mutable_paths_derive_from_storage_dir(monkeypatch):
    # 개별 경로 env가 없으면 STORAGE_DIR 기준으로 파생된다
    monkeypatch.delenv("SCRAPED_CONTENTS_PATH", raising=False)
    assert storage._mutable_path("SCRAPED_CONTENTS_PATH", "x.json") == os.path.join(
        storage.STORAGE_DIR, "x.json"
    )


def test_explicit_env_overrides_storage_dir(monkeypatch):
    monkeypatch.setenv("SCRAPED_CONTENTS_PATH", "/custom/path.json")
    assert storage._mutable_path("SCRAPED_CONTENTS_PATH", "x.json") == "/custom/path.json"
