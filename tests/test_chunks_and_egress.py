import json
from dataclasses import dataclass
from fluxmonad import Flux


@dataclass
class UserDto:
    name: str
    age: int


def test_chunk_and_batch():
    data = [1, 2, 3, 4, 5, 6, 7]
    assert Flux(data).chunk(3).collect() == [[1, 2, 3], [4, 5, 6], [7]]
    assert Flux(data).batch(2).collect() == [[1, 2], [3, 4], [5, 6], [7]]


def test_sliding_window():
    data = [1, 2, 3, 4, 5]
    # Окно размера 3 с шагом 1
    assert Flux(data).window(size=3, step=1).collect() == [
        [1, 2, 3],
        [2, 3, 4],
        [3, 4, 5],
    ]


def test_cast_to_dataclass():
    raw_records = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]
    users = Flux(raw_records).cast(lambda r: UserDto(**r)).collect()

    assert all(isinstance(u, UserDto) for u in users)
    assert users[0].name == "Alice"


def test_export_to_json_and_csv(tmp_path):
    data = [{"id": 1, "city": "Rome"}, {"id": 2, "city": "Milan"}]

    json_file = tmp_path / "out.json"
    Flux(data).to_json(json_file)
    with open(json_file, encoding="utf-8") as f:
        assert json.load(f) == data

    csv_file = tmp_path / "out.csv"
    Flux(data).to_csv(csv_file)
    content = csv_file.read_text(encoding="utf-8")
    assert "id,city" in content
    assert "1,Rome" in content
    assert "2,Milan" in content