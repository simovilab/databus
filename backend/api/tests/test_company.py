"""API tests for the live CompanyViewSet (`GET /api/company/`).

CompanySerializer previously declared a PrimaryKeyRelatedField for a
non-existent `agency` attribute (the Company model's field is the M2M
`linked_agency`); these tests exercise the real field end to end.
"""

import pytest

from feed.models import Agency
from operations.models import Company


@pytest.mark.django_db
def test_list_serializes_linked_agency(api_client, agency: Agency):
    """Listing a Company with a linked agency serializes linked_agency as a list of agency PKs."""
    company = Company.objects.create(id="company-1", name="Test Transit Co.")
    company.linked_agency.set([agency])

    response = api_client.get("/api/company/")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    # HyperlinkedModelSerializer swaps the pk for a `url` field rather than
    # exposing `id` directly, so identify the row by name and check the URL
    # embeds the pk instead.
    assert body[0]["name"] == "Test Transit Co."
    assert "company-1" in body[0]["url"]
    # HyperlinkedModelSerializer represents the M2M as hyperlinks too, one per
    # linked agency.
    assert len(body[0]["linked_agency"]) == 1
    assert f"/api/agency/{agency.pk}/" in body[0]["linked_agency"][0]


@pytest.mark.django_db
def test_list_serializes_company_with_no_linked_agency(api_client, db):
    """A Company with no linked agencies still serializes, with an empty linked_agency list."""
    Company.objects.create(id="company-2", name="Agency-less Co.")

    response = api_client.get("/api/company/")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["linked_agency"] == []
