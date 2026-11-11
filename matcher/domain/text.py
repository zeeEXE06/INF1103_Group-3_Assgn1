"""
Text helpers shared by the domain classes.
"""


def clean_strings(values):
    """A copy of a list of strings, trimmed and without blanks."""
    return [str(value).strip() for value in values if str(value).strip()]
