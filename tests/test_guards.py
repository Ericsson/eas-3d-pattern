# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2025-2026 Ericsson
#
# Author: Mattia Milani <mattia.milani@ericsson.com>
#
# This file is part of eas-3d-pattern and is distributed under the terms of the
# MIT License. See the LICENSE file at the repository root for the full text,
# including the warranty disclaimer and redistribution conditions.
"""Tests for the ``verify`` check-and-raise guard.

Pins the polarity of the contract: ``verify`` raises when the condition is
*falsy* (the thing to verify does not hold) and is a no-op when it is *truthy*.
Getting this backwards is the easy mistake, so it is tested directly.
"""

from __future__ import annotations

import logging

import pytest

from eas_3d_pattern.util_func.guards import verify


class TestVerifyRaisesOnFalsy:
    """A falsy condition means the invariant failed, so ``verify`` must raise."""

    @pytest.mark.parametrize("falsy", [False, None, 0, "", [], {}, ()])
    def test_falsy_condition_raises(self, falsy: object):
        with pytest.raises(ValueError, match="boom"):
            verify(falsy, "boom")

    def test_default_exception_is_value_error(self):
        with pytest.raises(ValueError, match="boom"):
            verify(False, "boom")

    def test_custom_exception_class_is_raised(self):
        with pytest.raises(FileNotFoundError, match="missing"):
            verify(False, "missing", FileNotFoundError)

    def test_message_is_used_verbatim(self):
        with pytest.raises(ValueError, match="the exact message"):
            verify(None, "the exact message")

    def test_failure_is_logged_at_error_level(self, caplog):
        with (
            caplog.at_level(logging.ERROR, logger="eas_3d_pattern.util_func.guards"),
            pytest.raises(ValueError, match="logged message"),
        ):
            verify(False, "logged message")
        assert any("logged message" in r.message for r in caplog.records)


class TestVerifyPassesOnTruthy:
    """A truthy condition means the invariant holds, so ``verify`` is a no-op."""

    @pytest.mark.parametrize("truthy", [True, 1, "x", [0], {"a": 1}, (0,)])
    def test_truthy_condition_does_not_raise(self, truthy: object):
        verify(truthy, "should not raise")

    def test_returns_none(self):
        assert verify(True, "ok") is None

    def test_truthy_does_not_log(self, caplog):
        with caplog.at_level(logging.ERROR, logger="eas_3d_pattern.util_func.guards"):
            verify(True, "should not be logged")
        assert not caplog.records
