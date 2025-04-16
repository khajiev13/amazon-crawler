import time
import functools
import logging
from typing import Any, Callable, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])

def print_timing(func: F) -> F:
    """Decorator to print the execution time of a function."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        logging.info(f"Function '{func.__name__}' executed in {end - start:.2f} seconds.")
        return result
    return cast(F, wrapper)
