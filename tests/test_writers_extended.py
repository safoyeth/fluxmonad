import pytest
from fluxmonad import Flux

# Опциональные проверки с пропуском, если библиотеки не установлены в окружении
yaml_installed = False
try:
    import yaml
    yaml_installed = True
except ImportError:
    pass

openpyxl_installed = False
try:
    import openpyxl
    openpyxl_installed = True
except ImportError:
    pass


@pytest.mark.skipif(not yaml_installed, reason="PyYAML не установлен")
def test_export_yaml(tmp_path):
    data = [{"name": "Alice", "skills": ["Python", "Rust"]}]
    target = tmp_path / "out.yaml"

    Flux(data).toYaml(target)

    with open(target, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    assert loaded == data


@pytest.mark.skipif(not openpyxl_installed, reason="openpyxl не установлен")
def test_export_and_read_excel(tmp_path):
    data = [
        {"id": 1, "title": "Keyboard", "price": 100},
        {"id": 2, "title": "Mouse", "price": 50},
    ]
    target = tmp_path / "products.xlsx"

    # Запись через фасад
    Flux(data).to_excel(target, sheet_name="Catalog")

    # Чтение обратно через встроенный загрузчик
    loaded = Flux.from_excel(target, sheet_name="Catalog").collect()

    assert len(loaded) == 2
    assert loaded[0]["title"] == "Keyboard"
    assert loaded[1]["price"] == 50


def test_to_file_smart_csv(tmp_path):
    data = [{"a": 1, "b": 2}]
    target = tmp_path / "smart.csv"
    Flux(data).toFile(target)

    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert "a,b" in content