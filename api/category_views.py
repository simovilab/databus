"""
ViewSets for GTFS category endpoints.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class RouteTypeListView(APIView):
    """
    GET endpoint que devuelve los tipos de rutas de GTFS.
    """
    
    def get(self, request):
        route_types = [
            {
                "id": 0,
                "name": "Tram, Streetcar, Light rail",
                "description": "Any light rail or street level system within a metropolitan area."
            },
            {
                "id": 1,
                "name": "Subway, Metro",
                "description": "Any underground rail system within a metropolitan area."
            },
            {
                "id": 2,
                "name": "Rail",
                "description": "Used for intercity or long-distance travel."
            },
            {
                "id": 3,
                "name": "Bus",
                "description": "Used for short- and long-distance bus routes."
            },
            {
                "id": 4,
                "name": "Ferry",
                "description": "Used for short- and long-distance boat service."
            },
            {
                "id": 5,
                "name": "Cable tram",
                "description": "Used for street-level rail cars where the cable runs beneath the vehicle (e.g., cable car in San Francisco)."
            },
            {
                "id": 6,
                "name": "Aerial lift, suspended cable car",
                "description": "Cable transport where cabins, cars, gondolas or open chairs are suspended by means of one or more cables."
            },
            {
                "id": 7,
                "name": "Funicular",
                "description": "Any rail system designed for steep inclines."
            },
            {
                "id": 11,
                "name": "Trolleybus",
                "description": "Electric buses that draw power from overhead wires using poles."
            },
            {
                "id": 12,
                "name": "Monorail",
                "description": "Railway in which the track consists of a single rail or a beam."
            }
        ]
        
        return Response(route_types, status=status.HTTP_200_OK)


class LocationTypeListView(APIView):
    """
    GET endpoint para tipos de ubicaciones de paradas.
    """
    
    def get(self, request):
        location_types = [
            {
                "id": 0,
                "name": "Stop or Platform",
                "description": "A location where passengers board or disembark from a transit vehicle."
            },
            {
                "id": 1,
                "name": "Station",
                "description": "A physical structure or area that contains one or more platforms."
            },
            {
                "id": 2,
                "name": "Entrance/Exit",
                "description": "A location where passengers can enter or exit a station."
            },
            {
                "id": 3,
                "name": "Generic Node",
                "description": "A location within a station used for linking pathways."
            },
            {
                "id": 4,
                "name": "Boarding Area",
                "description": "A specific location on a platform where passengers can board/alight."
            }
        ]
        
        return Response(location_types, status=status.HTTP_200_OK)


class WheelchairAccessibilityListView(APIView):
    """
    GET endpoint para niveles de accesibilidad en silla de ruedas.
    """
    
    def get(self, request):
        wheelchair_accessibility = [
            {
                "id": 0,
                "name": "No information",
                "description": "No accessibility information available."
            },
            {
                "id": 1,
                "name": "Accessible",
                "description": "Vehicle/stop is accessible to riders in wheelchairs."
            },
            {
                "id": 2,
                "name": "Not accessible",
                "description": "Vehicle/stop is not accessible to riders in wheelchairs."
            }
        ]
        
        return Response(wheelchair_accessibility, status=status.HTTP_200_OK)


class PickupDropoffTypeListView(APIView):
    """
    GET endpoint para tipos de recogida y bajada de pasajeros.
    """
    
    def get(self, request):
        pickup_dropoff_types = [
            {
                "id": 0,
                "name": "Regularly scheduled",
                "description": "Regularly scheduled pickup/drop off."
            },
            {
                "id": 1,
                "name": "Not available",
                "description": "No pickup/drop off available."
            },
            {
                "id": 2,
                "name": "Must phone agency",
                "description": "Must phone agency to arrange pickup/drop off."
            },
            {
                "id": 3,
                "name": "Must coordinate with driver",
                "description": "Must coordinate with driver to arrange pickup/drop off."
            }
        ]
        
        return Response(pickup_dropoff_types, status=status.HTTP_200_OK)


class PaymentMethodListView(APIView):
    """
    GET endpoint para métodos de pago de tarifas.
    """
    
    def get(self, request):
        payment_methods = [
            {
                "id": 0,
                "name": "Paid on board",
                "description": "Fare is paid on board."
            },
            {
                "id": 1,
                "name": "Paid before boarding",
                "description": "Fare must be paid before boarding."
            }
        ]
        
        return Response(payment_methods, status=status.HTTP_200_OK)


class TransferTypeListView(APIView):
    """
    GET endpoint para tipos de transferencia entre rutas.
    """
    
    def get(self, request):
        transfer_types = [
            {
                "id": 0,
                "name": "Recommended transfer point",
                "description": "Recommended transfer point between routes."
            },
            {
                "id": 1,
                "name": "Timed transfer point",
                "description": "Timed transfer between routes. Departing vehicle waits for arriving vehicle."
            },
            {
                "id": 2,
                "name": "Minimum transfer time",
                "description": "Transfer requires a minimum amount of time between arrival and departure."
            },
            {
                "id": 3,
                "name": "Not possible",
                "description": "Transfers are not possible between routes at this location."
            }
        ]
        
        return Response(transfer_types, status=status.HTTP_200_OK)
