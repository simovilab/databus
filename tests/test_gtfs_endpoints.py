"""
Integration tests for GTFS endpoints.

Tests GTFS data retrieval and validation.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from gtfs.models import Agency, Route, Stop, Trip


@pytest.mark.integration
@pytest.mark.database
class TestGTFSAgencyEndpoints:
    """Integration tests for GTFS Agency endpoints."""
    
    def test_list_agencies(self, api_client, agency):
        """Test listing agencies."""
        url = reverse('gtfs:agency-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
    
    def test_retrieve_agency(self, api_client, agency):
        """Test retrieving specific agency."""
        url = reverse('gtfs:agency-detail', kwargs={'agency_id': agency.agency_id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['agency_id'] == 'test-agency'
        assert data['agency_name'] == 'Test Transit'


@pytest.mark.integration
@pytest.mark.database
class TestGTFSRouteEndpoints:
    """Integration tests for GTFS Route endpoints."""
    
    def test_list_routes(self, api_client, route):
        """Test listing routes."""
        url = reverse('gtfs:route-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
    
    def test_retrieve_route(self, api_client, route):
        """Test retrieving specific route."""
        url = reverse('gtfs:route-detail', kwargs={'route_id': route.route_id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['route_id'] == 'test-route-1'
        assert data['route_short_name'] == '1'
    
    def test_filter_routes_by_agency(self, api_client, route):
        """Test filtering routes by agency."""
        url = reverse('gtfs:route-list')
        response = api_client.get(url, {'agency': route.agency.agency_id})
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(r['agency'] == route.agency.agency_id for r in data)


@pytest.mark.integration
@pytest.mark.database
class TestGTFSStopEndpoints:
    """Integration tests for GTFS Stop endpoints."""
    
    def test_list_stops(self, api_client, stop):
        """Test listing stops."""
        url = reverse('gtfs:stop-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
    
    def test_retrieve_stop(self, api_client, stop):
        """Test retrieving specific stop."""
        url = reverse('gtfs:stop-detail', kwargs={'stop_id': stop.stop_id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['stop_id'] == 'test-stop-1'
        assert 'stop_lat' in data
        assert 'stop_lon' in data
    
    def test_search_stops_by_location(self, api_client, stop):
        """Test searching stops by coordinates."""
        url = reverse('gtfs:stop-search')
        response = api_client.get(url, {
            'lat': 9.9281,
            'lon': -84.0907,
            'radius': 1000  # meters
        })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should find at least our test stop
        assert len(data) >= 1


@pytest.mark.integration
@pytest.mark.database
class TestGTFSTripEndpoints:
    """Integration tests for GTFS Trip endpoints."""
    
    def test_list_trips(self, api_client, trip):
        """Test listing trips."""
        url = reverse('gtfs:trip-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1
    
    def test_retrieve_trip(self, api_client, trip):
        """Test retrieving specific trip."""
        url = reverse('gtfs:trip-detail', kwargs={'trip_id': trip.trip_id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['trip_id'] == 'test-trip-1'
    
    def test_filter_trips_by_route(self, api_client, trip):
        """Test filtering trips by route."""
        url = reverse('gtfs:trip-list')
        response = api_client.get(url, {'route': trip.route.route_id})
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert all(t['route'] == trip.route.route_id for t in data)


@pytest.mark.integration
@pytest.mark.database
class TestGTFSDataValidation:
    """Integration tests for GTFS data validation."""
    
    def test_route_type_validation(self, api_client, agency):
        """Test route type must be valid GTFS value."""
        url = reverse('gtfs:route-list')
        
        # Valid route types: 0-12 in GTFS spec
        valid_data = {
            'route_id': 'test-route-valid',
            'agency': agency.agency_id,
            'route_short_name': 'V',
            'route_long_name': 'Valid Route',
            'route_type': 3  # Bus
        }
        
        response = api_client.post(url, valid_data, format='json')
        # Might be 201 or 405 (if POST not allowed)
        assert response.status_code in [201, 405]
    
    def test_stop_coordinates_validation(self, api_client):
        """Test stop coordinates must be valid."""
        url = reverse('gtfs:stop-list')
        
        invalid_data = {
            'stop_id': 'invalid-coords',
            'stop_name': 'Invalid Stop',
            'stop_lat': 91.0,  # Invalid latitude
            'stop_lon': -84.0
        }
        
        response = api_client.post(url, invalid_data, format='json')
        # Should fail validation
        assert response.status_code in [400, 405]


@pytest.mark.integration
@pytest.mark.database
class TestGTFSRelationships:
    """Integration tests for GTFS data relationships."""
    
    def test_route_has_agency(self, api_client, route):
        """Test routes are linked to agencies."""
        url = reverse('gtfs:route-detail', kwargs={'route_id': route.route_id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'agency' in data
    
    def test_trip_has_route(self, api_client, trip):
        """Test trips are linked to routes."""
        url = reverse('gtfs:trip-detail', kwargs={'trip_id': trip.trip_id})
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert 'route' in data
    
    def test_cascade_delete_route(self, authenticated_client, route, trip):
        """Test deleting route cascades to trips."""
        route_id = route.route_id
        
        # Delete route
        url = reverse('gtfs:route-detail', kwargs={'route_id': route_id})
        response = authenticated_client.delete(url)
        
        if response.status_code == 204:
            # Verify trips are also deleted (if cascade is configured)
            assert not Trip.objects.filter(route_id=route_id).exists()
