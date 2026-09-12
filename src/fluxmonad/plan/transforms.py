import itertools
from typing import Any, Callable, Iterator

from typing import Any, Callable, Iterator, Sequence, Union
from fluxmonad.accessors import project_exclude, project_select
from fluxmonad.expressions.base import Expression
from fluxmonad.expressions.parser import LambdaExpression

from fluxmonad.plan.node import Node


class MapNode(Node):
    """Стриминговое отображение элементов."""

    def __init__(self, parent: Node, func: Callable[[Any], Any]) -> None:
        super().__init__(parent=parent)
        self.func = func

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        return (self.func(item) for item in self.parent.evaluate())

    def explain_step(self) -> str:
        return f"MAP: {getattr(self.func, '__name__', str(self.func))}"


class FilterNode(Node):
    """Стриминговая фильтрация элементов по выражению или предикату."""

    def __init__(self, parent: Node, predicate_or_expr: Union[Callable[[Any], bool], Expression]) -> None:
        super().__init__(parent=parent)
        if isinstance(predicate_or_expr, Expression):
            self.expr = predicate_or_expr
        else:
            self.expr = LambdaExpression(predicate_or_expr)

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            if self.expr.evaluate(item):
                yield item

    def explain_step(self) -> str:
        return f"FILTER: {self.expr.explain()}"


class SelectNode(Node):
    """Стриминговая проекция: оставляет только указанные поля."""

    def __init__(self, parent: Node, fields: Sequence[str]) -> None:
        super().__init__(parent=parent)
        self.fields = list(fields)

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            yield project_select(item, self.fields)

    def explain_step(self) -> str:
        return f"SELECT: {', '.join(self.fields)}"


class ExcludeNode(Node):
    """Стриминговое исключение указанных полей."""

    def __init__(self, parent: Node, fields: Sequence[str]) -> None:
        super().__init__(parent=parent)
        self.fields = list(fields)

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            yield project_exclude(item, self.fields)

    def explain_step(self) -> str:
        return f"EXCLUDE: {', '.join(self.fields)}"


class TakeNode(Node):
    """Стриминговое ограничение количества элементов с ранней остановкой."""

    def __init__(self, parent: Node, count: int) -> None:
        super().__init__(parent=parent)
        if count < 0:
            raise ValueError("Параметр count не может быть отрицательным")
        self.count = count

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        return itertools.islice(self.parent.evaluate(), self.count)

    def explain_step(self) -> str:
        return f"TAKE: {self.count}"

class BindNode(Node):
    """
    Монадический узел (flat_map).
    Применяет функцию func к каждому элементу и разворачивает полученную
    последовательность (один уровень flatten) в потоковом режиме.
    """

    def __init__(self, parent: Node, func: Callable[[Any], Any]) -> None:
        super().__init__(parent=parent)
        self.func = func

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            sub_result = self.func(item)
            # Поддерживаем как обычные Iterable, так и инстансы Flux или генераторы
            for sub_item in sub_result:
                yield sub_item

    def explain_step(self) -> str:
        return f"BIND: {getattr(self.func, '__name__', str(self.func))}"