import json
import pytest
from fluxmonad import Flux


def test_flux_from_json_string():
    raw_json = '[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]'
    res = Flux.from_json(raw_json).select("name").collect()
    assert res == [{"name": "A"}, {"name": "B"}]


def test_flux_from_jsonl(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text('{"id": 1, "val": 10}\n{"id": 2, "val": 20}\n', encoding="utf-8")

    res = Flux.from_json(f, lines=True).when(val__gt=15).collect()
    assert res == [{"id": 2, "val": 20}]


def test_flux_from_csv(tmp_path):
    f = tmp_path / "users.csv"
    f.write_text("name,age,dept\nAlice,30,IT\nBob,20,HR\nCharlie,25,IT\n", encoding="utf-8")

    res = (
        Flux.from_csv(f)
        .when(dept="IT")
        .select("name")
        .collect()
    )
    assert res == [{"name": "Alice"}, {"name": "Charlie"}]


def test_flux_from_file_auto_detection(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("item,qty\napple,5\nbanana,10\n", encoding="utf-8")

    res = Flux.from_file(f).collect()
    assert len(res) == 2
    assert res[0]["item"] == "apple"