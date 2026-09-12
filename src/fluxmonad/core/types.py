from typing import Any, Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")
F = TypeVar("F", bound=Callable[..., Any])

Predicate = Callable[[T], bool]
Transform = Callable[[T], R]
KeySelector = Callable[[T], Any]


def alias_for(target_func: Callable[..., Any]) -> Callable[[F], F]:
    """
    Decorator for method aliases.
    Copies the docstring of the target method and appends an explicit alias note.
    """
    def decorator(alias_method: F) -> F:
        orig_doc = (target_func.__doc__ or "").strip()
        orig_name = target_func.__name__
        alias_method.__doc__ = (
            f"Alias for :meth:`{orig_name}` (Алиас для метода :meth:`{orig_name}`).\n\n"
            f"{orig_doc}"
        )
        return alias_method

    return decorator