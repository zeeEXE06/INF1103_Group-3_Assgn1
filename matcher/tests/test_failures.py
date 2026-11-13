"""
What the user sees when something goes wrong. Each test is one row of the
error-handling matrix: the failure, the message shown, and that the app
keeps working (no crash, no half-saved results).
"""

from unittest.mock import patch

from django.test import Client, override_settings
from django.urls import reverse

from ..views import EmployerResultsView
from .test_app import text


# ---------- Errors nobody planned for ----------

@override_settings(DEBUG=False)
def test_unknown_page_shows_a_friendly_404():
    response = Client().get("/no-such-page/")
    assert response.status_code == 404
    assert "Page not found" in text(response) and "Go to the home page" in text(response)


@override_settings(DEBUG=False)
def test_unexpected_error_shows_a_friendly_500_page():
    client = Client(raise_request_exception=False)
    with patch.object(EmployerResultsView, "get", side_effect=RuntimeError("bug")):
        response = client.get(reverse("matcher:employer_results"))
    assert response.status_code == 500
    assert "Something went wrong" in text(response) and "RuntimeError" not in text(response)
