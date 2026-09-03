"""The application's version and build date.

Kept as plain constants with no imports so anything can read them cheaply --
the PyInstaller spec, the Info dialog, the window title and the tests.

`DOC_VERSION` in docs/help/source/document_registry.py is deliberately
separate: a documentation correction should not imply a new application
build. Bump them together when shipping.
"""

APP_VERSION = "2.3.0"

# ISO-8601, so it sorts and parses. Update alongside APP_VERSION.
BUILD_DATE = "2026-09-03"

# The product name as users see it.
APP_NAME = "N Video Converter"
APP_SHORT_NAME = "NVC"


def build_date_display() -> str:
    """The build date as a reader wants it: '3 September 2026'.

    Falls back to the raw string rather than raising, so a malformed constant
    shows up in the Info dialog instead of breaking it.
    """
    try:
        from datetime import date
        parsed = date.fromisoformat(BUILD_DATE)
    except (ImportError, TypeError, ValueError):
        return BUILD_DATE
    return f"{parsed.day} {parsed:%B} {parsed.year}"


def version_line() -> str:
    """'N Video Converter 2.3.0 - 3 September 2026', for the Info dialog."""
    return f"{APP_NAME} {APP_VERSION} — {build_date_display()}"
