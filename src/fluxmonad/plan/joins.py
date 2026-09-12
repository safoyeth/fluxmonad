import collections
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from fluxmonad.accessors import get_value
from fluxmonad.plan.node import Node


class JoinNode(Node):
    """
    Узел объединения двух потоков данных (Hash Join).
    Поддерживает inner и left outer join.
    """

    def __init__(
        self,
        left_parent: Node,
        right_parent: Node,
        left_on: Union[str, Callable[[Any], Any]],
        right_on: Union[str, Callable[[Any], Any]],
        how: str = "inner",
    ) -> None:
        super().__init__(parent=left_parent)
        self.right_parent = right_parent
        self.left_on = left_on
        self.right_on = right_on
        self.how = how.lower()

        if self.how not in ("inner", "left"):
            raise ValueError(f"Поддерживаются только типы join 'inner' и 'left', получено: {how}")

    @property
    def is_barrier(self) -> bool:
        # Правая сторона материализуется в хэш-таблицу
        return True

    def _extract_key(self, item: Any, selector: Union[str, Callable[[Any], Any]]) -> Any:
        if callable(selector):
            return selector(item)
        return get_value(item, selector, default=None)

    def evaluate(self) -> Iterator[Dict[str, Any]]:
        assert self.parent is not None

        # 1. Построение хэш-таблицы по правой стороне (Build phase)
        right_hash_table: collections.defaultdict[Any, List[Any]] = collections.defaultdict(list)
        for r_item in self.right_parent.evaluate():
            r_key = self._extract_key(r_item, self.right_on)
            right_hash_table[r_key].append(r_item)

        # 2. Потоковый проход по левой стороне (Probe phase)
        for l_item in self.parent.evaluate():
            l_key = self._extract_key(l_item, self.left_on)
            matches = right_hash_table.get(l_key, [])

            if matches:
                for match in matches:
                    yield self._merge_records(l_item, match)
            elif self.how == "left":
                yield self._merge_records(l_item, None)

    def _merge_records(self, left_item: Any, right_item: Optional[Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}

        if isinstance(left_item, dict):
            merged.update(left_item)
        elif hasattr(left_item, "__dict__"):
            merged.update({k: v for k, v in left_item.__dict__.items() if not k.startswith("_")})
        else:
            merged["left"] = left_item

        if right_item is not None:
            if isinstance(right_item, dict):
                merged.update(right_item)
            elif hasattr(right_item, "__dict__"):
                merged.update({k: v for k, v in right_item.__dict__.items() if not k.startswith("_")})
            else:
                merged["right"] = right_item

        return merged

    def explain_step(self) -> str:
        return f"JOIN ({self.how.upper()}): left_on={self.left_on}, right_on={self.right_on} (barrier=True)"