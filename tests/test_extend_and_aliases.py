from fluxmonad import Flux


def test_extend_template_list():
    names = Flux([{"name": "S", "surname": "T"}])
    result = (
        names.extend("fullname", ["name", " ", "surname"])
        .select("fullname")
        .collect()
    )
    assert result == [{"fullname": "S T"}]


def test_camel_case_and_snake_case_chaining():
    data = [
        {"name": "Ivan", "age": 25, "dept": "IT"},
        {"name": "Anna", "age": 17, "dept": "HR"},
        {"name": "Petr", "age": 30, "dept": "IT"},
    ]

    # Проверка вызова полностью в camelCase
    res_camel = (
        Flux(data)
        .filterBy(age__gte=18)
        .sortBy("-age")
        .limit(1)
        .toList()
    )
    assert res_camel == [{"name": "Petr", "age": 30, "dept": "IT"}]

    # Проверка вызова полностью в snake_case
    res_snake = (
        Flux(data)
        .filter_by(age__gte=18)
        .sort_by("-age")
        .limit(1)
        .to_list()
    )
    assert res_snake == [{"name": "Petr", "age": 30, "dept": "IT"}]