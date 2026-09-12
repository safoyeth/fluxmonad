from fluxmonad.expressions.logical import And
from fluxmonad.plan.node import Node
from fluxmonad.plan.transforms import FilterNode, TakeNode


class PlanOptimizer:
    """Оптимизатор графа выполнения потока."""

    @classmethod
    def optimize(cls, node: Node) -> Node:
        """Рекурсивно сжимает и перестраивает цепочку узлов."""
        if node.parent is None:
            return node

        optimized_parent = cls.optimize(node.parent)
        node.parent = optimized_parent

        # 1. Сворачивание нескольких Take подряд: Take(A) -> Take(B) === Take(min(A, B))
        if isinstance(node, TakeNode) and isinstance(optimized_parent, TakeNode):
            min_count = min(node.count, optimized_parent.count)
            optimized_parent.count = min_count
            return optimized_parent

        # 2. Слияние фильтров: Filter(A) -> Filter(B) === Filter(A AND B)
        if isinstance(node, FilterNode) and isinstance(optimized_parent, FilterNode):
            combined_expr = And(optimized_parent.expr, node.expr)
            merged_filter = FilterNode(optimized_parent.parent, combined_expr)
            return merged_filter

        return node