"""Shared pytest configuration for Qt tests."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
