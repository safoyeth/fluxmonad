import copy
from typing import Any, List, Optional, Set

from fluxmonad.expressions.logical import And
from fluxmonad.plan.node import Node
from fluxmonad.plan.source import SourceNode
from fluxmonad.plan.transforms import (
    ExtendNode,
    FilterNode,
    RenameNode,
    SkipNode,
    TakeNode,
    TapNode,
)

def get_filter_fields(expr: Any) -> Set[str]:
    """Извлекает имена полей из предиката, игнорируя пустые заглушки базовых классов."""
    fields: Set[str] = set()
    if expr is None:
        return fields

    # 1. Проверяем referenced_fields, но учитываем ТОЛЬКО непустой результат
    if hasattr(expr, "referenced_fields"):
        try:
            rf = expr.referenced_fields
            if rf:
                return {str(f).split(".")[0].strip() for f in rf}
        except Exception:
            pass

    # 2. Проверяем вложенные выражения/обертки
    for attr in ("inner", "expr", "predicate"):
        if hasattr(expr, attr):
            inner = getattr(expr, attr)
            if inner is not expr and inner is not None:
                res = get_filter_fields(inner)
                if res:
                    return res

    # 3. Извлекаем поле из атрибутов левой части / имени поля
    for attr in ("left", "field", "field_name", "path", "name", "column", "field_path"):
        val = getattr(expr, attr, None)
        if val is not None:
            if isinstance(val, str):
                fields.add(val.split(".")[0].strip())
            elif hasattr(val, "path"):
                fields.add(str(val.path).split(".")[0].strip())
            elif hasattr(val, "name"):
                fields.add(str(val.name).split(".")[0].strip())

    # 4. Если в выражении есть список подвыражений (And, Or)
    if hasattr(expr, "expressions"):
        for sub in getattr(expr, "expressions", []):
            fields.update(get_filter_fields(sub))

    return fields


class PlanOptimizer:
    @classmethod
    def optimize(cls, node: Node) -> Node:
        # 1. Извлекаем цепочку от Source к Terminal (клонируя узлы)
        nodes: List[Node] = []
        curr: Optional[Node] = node
        while curr is not None:
            nodes.append(copy.copy(curr))
            curr = curr.parent
        nodes.reverse()

        if not nodes:
            return node

        # 2. Predicate Pushdown: проталкиваем FilterNode к началу
        changed = True
        while changed:
            changed = False
            for i in range(len(nodes) - 1, 0, -1):
                curr_node = nodes[i]
                prev_node = nodes[i - 1]

                if isinstance(curr_node, FilterNode) and not isinstance(prev_node, SourceNode):
                    if cls._can_swap(filter_node=curr_node, prev_node=prev_node):
                        nodes[i - 1], nodes[i] = curr_node, prev_node
                        changed = True

        # 3. Сворачивание смежных узлов (Take/Skip/Filter)
        collapsed: List[Node] = []
        for n in nodes:
            if not collapsed:
                collapsed.append(n)
                continue

            top = collapsed[-1]

            if isinstance(n, TakeNode) and n.count == 0:
                collapsed = [SourceNode([])]
                break

            if isinstance(n, TakeNode) and isinstance(top, TakeNode):
                top.count = min(top.count, n.count)
                continue

            if isinstance(n, SkipNode) and isinstance(top, SkipNode):
                top.count = top.count + n.count
                continue

            if isinstance(n, FilterNode) and isinstance(top, FilterNode):
                top.expr = And(top.expr, n.expr)
                continue

            collapsed.append(n)

        # 4. Восстанавливаем связи parent
        collapsed[0].parent = None
        for i in range(1, len(collapsed)):
            collapsed[i].parent = collapsed[i - 1]

        return collapsed[-1]

    @classmethod
    def _can_swap(cls, filter_node: FilterNode, prev_node: Node) -> bool:
        filter_fields = get_filter_fields(filter_node.expr)

        # Через TapNode сдвигать можно всегда
        if isinstance(prev_node, TapNode):
            return True

        # Если не удалось точно определить поля фильтра — перестановка с изменением схемы НЕБЕЗОПАСНА
        if not filter_fields:
            return False

        # Через ExtendNode
        if isinstance(prev_node, ExtendNode):
            target = getattr(prev_node, "target_field", getattr(prev_node, "name", None))
            if not target:
                return False

            target_str = str(target).split(".")[0].strip()

            # Если целевое поле совпадает с зависимостью фильтра — ЗАПРЕЩАЕМ перестановку
            if target_str in filter_fields:
                return False

            # Фильтр проверяет другие поля (например 'age'), а создается 'label' — РАЗРЕШАЕМ
            return True

        # Через RenameNode
        if isinstance(prev_node, RenameNode):
            keys = set(prev_node.mapping.keys()) | set(prev_node.mapping.values())
            if filter_fields & keys:
                return False
            return True

        return False