from fluxmonad import Flux


def test_union():
    f1 = Flux([1, 2, 3])
    f2 = Flux([4, 5])
    assert f1.union(f2).collect() == [1, 2, 3, 4, 5]


def test_intersection():
    f1 = Flux([1, 2, 3, 4])
    f2 = Flux([3, 4, 5, 6])
    assert f1.intersection(f2).collect() == [3, 4]


def test_difference():
    f1 = Flux([1, 2, 3, 4])
    f2 = Flux([2, 4])
    assert f1.difference(f2).collect() == [1, 3]


def test_rename():
    users = Flux([{"id": 1, "uname": "Alice"}])
    res = users.rename(uname="username").collect()
    assert res == [{"id": 1, "username": "Alice"}]


def test_group_aggregate():
    employees = [
        {"name": "Alice", "dept": "IT", "salary": 100},
        {"name": "Bob", "dept": "HR", "salary": 70},
        {"name": "Charlie", "dept": "IT", "salary": 150},
    ]

    stats = (
        Flux(employees)
        .groupby("dept")
        .map(lambda g: g.aggregate(
            total_salary="sum:salary",
            avg_salary="avg:salary",
            emp_count="count",
        ))
        .collect()
    )

    assert stats == [
        {"key": "IT", "total_salary": 250, "avg_salary": 125.0, "emp_count": 2},
        {"key": "HR", "total_salary": 70, "avg_salary": 70.0, "emp_count": 1},
    ]