# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Small check-and-raise guards for input validation.

Pure helpers that collapse the repeated "log an error and raise" pattern into a
single declarative call, keeping constructors and loaders readable.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def verify(condition: object,
           msg: str,
           raiser: type[Exception] = ValueError) -> None:
    """Raise ``raiser`` with ``msg`` when ``condition`` is falsy.

    Args:
        condition (object): Value treated as a predicate; a falsy value
            (``None``, ``False``, empty container) triggers the failure.
        msg (str): Message used both for the log record and the raised error.
        raiser (type[Exception]): Exception class to raise. Defaults to
            ``ValueError``.

    Raises:
        Exception: An instance of ``raiser`` when ``condition`` is falsy.
    """
    if not condition:
        logger.error(msg)
        raise raiser(msg)
