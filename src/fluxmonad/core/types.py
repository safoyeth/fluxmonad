from typing import Any, Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")
F = TypeVar("F", bound=Callable[..., Any])

Predicate = Callable[[T], bool]
Transform = Callable[[T], R]
KeySelector = Callable[[T], Any]


def alias_for(target_func: Callable[..., Any]) -> Callable[[F], F]:
    """
    Декоратор для методов-алиасов.
    Копирует docstring целевого метода, добавляя явную пометку об алиасе.
    """
    def decorator(alias_method: F) -> F:
        orig_doc = (target_func.__doc__ or "").strip()
        orig_name = target_func.__name__
        alias_method.__doc__ = (
            f"Алиас для метода :meth:`{orig_name}`.\n\n"
            f"{orig_doc}"
        )
        return alias_method

    return decorator