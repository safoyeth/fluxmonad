from typing import Any, Callable, TypeVar

T = TypeVar("T")
R = TypeVar("R")

Predicate = Callable[[T], bool]
Transform = Callable[[T], R]
KeySelector = Callable[[T], Any]