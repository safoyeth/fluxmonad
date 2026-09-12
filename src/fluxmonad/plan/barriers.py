from typing import Any, Callable, Iterator, List, Sequence, Tuple, Union
from fluxmonad.accessors import MISSING, get_value
from fluxmonad.plan.node import Node


class _ComparableWrapper:
    """Обертка для безопасного сравнения значений с поддержкой DESC-направления."""

    __slots__ = ("value", "descending")

    def __init__(self, value: Any, descending: bool = False) -> None:
        self.value = value
        self.descending = descending

    def __lt__(self, other: "_ComparableWrapper") -> bool:
        # Если значения равны — ни одно не меньше другого
        if self.value == other.value:
            return False

        # Обработка отсутствующих значений и None
        if self.value is MISSING or self.value is None:
            return not self.descending
        if other.value is MISSING or other.value is None:
            return self.descending

        try:
            less = self.value < other.value
        except TypeError:
            less = str(self.value) < str(other.value)

        # Если задан порядок убывания, переворачиваем логику <
        return not less if self.descending else less

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, _ComparableWrapper):
            return False
        return self.value == other.value


class SortNode(Node):
    """
    Барьерный узел сортировки потока.
    Полностью материализует входной поток перед упорядочиванием.
    """

    def __init__(
        self,
        parent: Node,
        keys: Sequence[Union[str, Callable[[Any], Any]]],
        reverse: bool = False,
    ) -> None:
        super().__init__(parent=parent)
        self.keys = list(keys)
        self.default_reverse = reverse

    @property
    def is_barrier(self) -> bool:
        return True

    def _extract_sort_tuple(self, item: Any) -> Tuple[Any, ...]:
        result = []
        for key in self.keys:
            if callable(key):
                val = key(item)
                result.append(_ComparableWrapper(val, descending=False))
            elif isinstance(key, str):
                is_desc = key.startswith("-")
                path = key[1:] if is_desc else key
                val = get_value(item, path, default=MISSING)
                result.append(_ComparableWrapper(val, descending=is_desc))
            else:
                raise TypeError(f"Ключ сортировки должен быть строкой или callable, получен {type(key)}")
        return tuple(result)

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        materialized: List[Any] = list(self.parent.evaluate())

        if not self.keys:
            materialized.sort(reverse=self.default_reverse)
        else:
            materialized.sort(
                key=self._extract_sort_tuple,
                reverse=self.default_reverse,
            )

        return iter(materialized)

    def explain_step(self) -> str:
        keys_str = ", ".join(
            getattr(k, "__name__", str(k)) for k in self.keys
        ) or "natural"
        return f"SORT: {keys_str} (barrier=True)"