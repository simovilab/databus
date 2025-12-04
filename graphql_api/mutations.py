import strawberry
from strawberry.types import Info
from typing import List
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from gtfs.models import Agency, Feed
from .types import CreateAgencyInput, CreateAgencyPayload, agency_to_type
from .permissions import IsStaff


@strawberry.type
class Mutation:
    @strawberry.mutation(permission_classes=[IsStaff])
    def create_agency(
        self, info: Info, input: CreateAgencyInput
    ) -> CreateAgencyPayload:
        ### aca crearemos nuevas agencias
        errors: List[str] = []

        # Requerimientos 
        if not input.agency_id or not input.agency_id.strip():
            errors.append("No introdujo el ID de la agencia")

        if not input.agency_url or not input.agency_url.strip():
            errors.append("No introdujo la URL de la agencia")

        # Check if feed exists
        try:
            feed = Feed.objects.get(id=input.feed_id)
        except Feed.DoesNotExist:
            errors.append(f"Este feed {input.feed_id} no existe")
            return CreateAgencyPayload(agency=None, errors=errors, success=False)

        if errors:
            return CreateAgencyPayload(agency=None, errors=errors, success=False)

        try:
            # Create the agency
            agency = Agency.objects.create(
                feed=feed,
                agency_id=input.agency_id,
                agency_name=input.agency_name.strip(),
                agency_url=input.agency_url.strip(),
                agency_timezone=input.agency_timezone.strip(),
                agency_lang=input.agency_lang.strip() if input.agency_lang else "",
                agency_phone=input.agency_phone.strip() if input.agency_phone else "",
                agency_fare_url=(
                    input.agency_fare_url.strip() if input.agency_fare_url else ""
                ),
                agency_email=input.agency_email.strip() if input.agency_email else "",
            )

            return CreateAgencyPayload(agency=agency_to_type(agency), errors=[], success=True)

        except IntegrityError as e:
            errors.append(f"Esta agencia ya Existe: {str(e)}")
            return CreateAgencyPayload(agency=None, errors=errors, success=False)

        except ValidationError as e:
            errors.append(f"Error: {str(e)}")
            return CreateAgencyPayload(agency=None, errors=errors, success=False)

        except Exception as e:
            errors.append(f"No se pudo crear agencia: {str(e)}")
            return CreateAgencyPayload(agency=None, errors=errors, success=False)
