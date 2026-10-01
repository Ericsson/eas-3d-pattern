# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Wall-clock timing decorator for profiling the pattern pipeline.

Prints to stdout rather than logging, so a timed run needs no logger
configuration and the output cannot be filtered out by a handler. The decorator
is meant for profiling sessions: leaving it applied costs one
``perf_counter`` pair and one ``print`` per call.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
R = TypeVar("R")

#: Prefix marking a timing line, so a run's timings are greppable.
TIMING_PREFIX = "[time_it]"

#: Milliseconds per second, for reporting.
MS_PER_S = 1000.0


def time_it(func: Callable[P, R]) -> Callable[P, R]:
    """Print the wall-clock execution time of ``func`` on every call.

    The timing is printed even when the call raises, so a failing stage still
    reports how long it ran before failing.

    Args:
        func (Callable[P, R]): Function or method to time.

    Returns:
        Callable[P, R]: ``func`` wrapped so each call prints its duration.

    Example:
        >>> @time_it
        ... def slow() -> int:
        ...     return sum(range(1000))
        >>> _ = slow()  # doctest: +SKIP
        [time_it] slow                                     0.02 ms
    """
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed_ms = (time.perf_counter() - start) * MS_PER_S
            print(f"{TIMING_PREFIX} {func.__qualname__:<45} {elapsed_ms:8.2f} ms")

    return wrapper
