from fluxmonad.expressions.logical import And
from fluxmonad.plan.node import Node
from fluxmonad.plan.source import SourceNode
from fluxmonad.plan.transforms import FilterNode, SkipNode, TakeNode


class PlanOptimizer:
    """Оптимизатор графа выполнения потока."""

    @classmethod
    def optimize(cls, node: Node) -> Node:
        """Рекурсивно сжимает и перестраивает цепочку узлов."""
        if node.parent is None:
            return node

        optimized_parent = cls.optimize(node.parent)
        node.parent = optimized_parent

        # 1. Take(0) -> мгновенно преобразуем в пустой источник
        if isinstance(node, TakeNode) and node.count == 0:
            return SourceNode([])

        # 2. Сворачивание нескольких Take подряд: Take(A) -> Take(B) === Take(min(A, B))
        if isinstance(node, TakeNode) and isinstance(optimized_parent, TakeNode):
            min_count = min(node.count, optimized_parent.count)
            optimized_parent.count = min_count
            return optimized_parent

        # 3. Сворачивание нескольких Skip подряд: Skip(A) -> Skip(B) === Skip(A + B)
        if isinstance(node, SkipNode) and isinstance(optimized_parent, SkipNode):
            total_skip = optimized_parent.count + node.count
            optimized_parent.count = total_skip
            return optimized_parent

        # 4. Слияние цепочки фильтров: Filter(A) -> Filter(B) === Filter(A AND B)
        if isinstance(node, FilterNode) and isinstance(optimized_parent, FilterNode):
            combined_expr = And(optimized_parent.expr, node.expr)
            merged_filter = FilterNode(optimized_parent.parent, combined_expr)
            return merged_filter

        return node