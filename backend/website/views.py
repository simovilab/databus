"""HTTP views for the website app."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

# Create your views here.


def index(request: HttpRequest) -> HttpResponse:
    """Render the public landing page."""
    return render(request, "index.html")
