import collections
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Union

from fluxmonad.accessors import get_value
from fluxmonad.plan.node import Node


class JoinNode(Node):
    """
    Узел объединения двух потоков данных (Hash Join).
    Поддерживает: 'inner', 'left', 'right', 'full'.
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

        valid_modes = ("inner", "left", "right", "full")
        if self.how not in valid_modes:
            raise ValueError(f"Поддерживаются типы join {valid_modes}, получено: {how}")

    @property
    def is_barrier(self) -> bool:
        return True

    def _extract_key(self, item: Any, selector: Union[str, Callable[[Any], Any]]) -> Any:
        if callable(selector):
            return selector(item)
        return get_value(item, selector, default=None)

    def evaluate(self) -> Iterator[Dict[str, Any]]:
        assert self.parent is not None

        # Build phase: хэшируем правую сторону
        right_hash_table: collections.defaultdict[Any, List[Any]] = collections.defaultdict(list)
        matched_right_indices: Set[int] = set()
        indexed_right_records: List[Any] = []

        right_idx = 0
        for r_item in self.right_parent.evaluate():
            r_key = self._extract_key(r_item, self.right_on)
            right_hash_table[r_key].append((right_idx, r_item))
            indexed_right_records.append(r_item)
            right_idx += 1

        # Probe phase: стримим левую сторону
        for l_item in self.parent.evaluate():
            l_key = self._extract_key(l_item, self.left_on)
            matches = right_hash_table.get(l_key, [])

            if matches:
                for r_idx, r_match in matches:
                    matched_right_indices.add(r_idx)
                    yield self._merge_records(l_item, r_match)
            elif self.how in ("left", "full"):
                yield self._merge_records(l_item, None)

        # Emit unmatched right records for right & full outer joins
        if self.how in ("right", "full"):
            for idx, r_item in enumerate(indexed_right_records):
                if idx not in matched_right_indices:
                    yield self._merge_records(None, r_item)

    def _merge_records(self, left_item: Optional[Any], right_item: Optional[Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}

        if left_item is not None:
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


class CrossJoinNode(Node):
    """Декартово произведение двух потоков (Cartesian Product)."""

    def __init__(self, left_parent: Node, right_parent: Node) -> None:
        super().__init__(parent=left_parent)
        self.right_parent = right_parent

    @property
    def is_barrier(self) -> bool:
        return True

    def evaluate(self) -> Iterator[Dict[str, Any]]:
        assert self.parent is not None
        # Материализуем правую сторону
        right_items: List[Any] = list(self.right_parent.evaluate())

        for l_item in self.parent.evaluate():
            for r_item in right_items:
                merged: Dict[str, Any] = {}
                if isinstance(l_item, dict):
                    merged.update(l_item)
                else:
                    merged["left"] = l_item

                if isinstance(r_item, dict):
                    merged.update(r_item)
                else:
                    merged["right"] = r_item
                yield merged

    def explain_step(self) -> str:
        return "CROSS JOIN (barrier=True)"