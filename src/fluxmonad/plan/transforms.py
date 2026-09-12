import itertools
from typing import Any, Callable, Iterator

from typing import Any, Callable, Iterator, Sequence, Union
from fluxmonad.accessors import project_exclude, project_select
from fluxmonad.accessors.resolver import MISSING, get_value
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

class SkipNode(Node):
    """Стриминговый пропуск первых n элементов."""

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
        return itertools.islice(self.parent.evaluate(), self.count, None)

    def explain_step(self) -> str:
        return f"SKIP: {self.count}"

class ExtendNode(Node):
    """
    Стриминговое добавление/обогащение элементов новым полем.
    Возвращает копию словаря или объекта с добавленным полем.
    """

    def __init__(self, parent: Node, field_name: str, rule: Any) -> None:
        super().__init__(parent=parent)
        self.field_name = field_name
        self.rule = rule

    @property
    def is_barrier(self) -> bool:
        return False

    def _compute_value(self, item: Any) -> Any:
        if callable(self.rule):
            return self.rule(item)

        if isinstance(self.rule, (list, tuple)):
            parts = []
            for part in self.rule:
                if isinstance(part, str):
                    # Если строка не является потенциальным путем (содержит пробелы и т.п.),
                    # используем её сразу как литерал
                    if " " in part or not part.strip():
                        parts.append(part)
                        continue

                    try:
                        val = get_value(item, part, default=MISSING)
                        parts.append(str(val) if val is not MISSING else part)
                    except ValueError:
                        # Если путь невалиден с точки зрения синтаксиса — берем как строковый литерал
                        parts.append(part)
                else:
                    parts.append(str(part))
            return "".join(parts)

        return self.rule

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for item in self.parent.evaluate():
            computed = self._compute_value(item)
            if isinstance(item, dict):
                new_item = dict(item)
                new_item[self.field_name] = computed
                yield new_item
            else:
                # Если передан пользовательский объект — обогащаем его поверхностную копию
                import copy
                new_obj = copy.copy(item)
                setattr(new_obj, self.field_name, computed)
                yield new_obj

    def explain_step(self) -> str:
        return f"EXTEND: {self.field_name}"