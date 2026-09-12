import collections
import copy
from typing import Any, Callable, Deque, Iterator, List, Optional, Union

from fluxmonad.accessors import get_value
from fluxmonad.plan.node import Node


class EnumerateNode(Node):
    """Стриминговое добавление порядкового номера/индекса к элементам."""

    def __init__(self, parent: Node, start: int = 0, field: Optional[str] = None) -> None:
        super().__init__(parent=parent)
        self.start = start
        self.field = field

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        for idx, item in enumerate(self.parent.evaluate(), start=self.start):
            if self.field is None:
                yield (idx, item)
            elif isinstance(item, dict):
                new_dict = dict(item)
                new_dict[self.field] = idx
                yield new_dict
            else:
                new_obj = copy.copy(item)
                setattr(new_obj, self.field, idx)
                yield new_obj

    def explain_step(self) -> str:
        return f"ENUMERATE: start={self.start}, field={self.field}"


class CumulativeSumNode(Node):
    """Стриминговый расчет нарастающего итога (running sum)."""

    def __init__(self, parent: Node, field: str, target_field: Optional[str] = None) -> None:
        super().__init__(parent=parent)
        self.field = field
        self.target_field = target_field or f"{field}_cumsum"

    @property
    def is_barrier(self) -> bool:
        return False

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        running_total: Union[int, float] = 0
        for item in self.parent.evaluate():
            val = get_value(item, self.field, default=0)
            if isinstance(val, (int, float)):
                running_total += val

            if isinstance(item, dict):
                new_item = dict(item)
                new_item[self.target_field] = running_total
                yield new_item
            else:
                new_obj = copy.copy(item)
                setattr(new_obj, self.target_field, running_total)
                yield new_obj

    def explain_step(self) -> str:
        return f"CUMSUM: {self.field} -> {self.target_field}"


class LagLeadNode(Node):
    """
    Аналитический узел LAG / LEAD.
    Использует ограниченный скользящий буфер (deque), не загружая весь поток в память.
    """

    def __init__(
        self,
        parent: Node,
        field: str,
        offset: int,
        target_field: Optional[str] = None,
        default: Any = None,
        is_lead: bool = False,
    ) -> None:
        super().__init__(parent=parent)
        if offset <= 0:
            raise ValueError("Смещение offset должно быть строго больше 0")
        self.field = field
        self.offset = offset
        self.target_field = target_field or (f"{field}_lead{offset}" if is_lead else f"{field}_lag{offset}")
        self.default = default
        self.is_lead = is_lead

    @property
    def is_barrier(self) -> bool:
        # Для lead требуется опережающий буфер размера offset + 1, но не материализация всего потока
        return False

    def _enrich(self, item: Any, value: Any) -> Any:
        if isinstance(item, dict):
            new_item = dict(item)
            new_item[self.target_field] = value
            return new_item
        new_obj = copy.copy(item)
        setattr(new_obj, self.target_field, value)
        return new_obj

    def evaluate(self) -> Iterator[Any]:
        assert self.parent is not None
        stream = self.parent.evaluate()

        if not self.is_lead:
            # LAG: храним историю прошлых значений
            history: Deque[Any] = collections.deque(maxlen=self.offset)
            for item in stream:
                lag_val = history[0] if len(history) == self.offset else self.default
                val = get_value(item, self.field, default=None)
                history.append(val)
                yield self._enrich(item, lag_val)
        else:
            # LEAD: храним буфер будущих записей
            buffer: Deque[Any] = collections.deque()
            for _ in range(self.offset):
                try:
                    buffer.append(next(stream))
                except StopIteration:
                    break

            for item in stream:
                lead_val = get_value(item, self.field, default=None)
                current_item = buffer.popleft()
                buffer.append(item)
                yield self._enrich(current_item, lead_val)

            # Оставшиеся в буфере элементы в конце потока
            while buffer:
                current_item = buffer.popleft()
                yield self._enrich(current_item, self.default)

    def explain_step(self) -> str:
        op = "LEAD" if self.is_lead else "LAG"
        return f"{op}: {self.field} (offset={self.offset}) -> {self.target_field}"