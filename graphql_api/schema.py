import strawberry
from .queries import Query
from .mutations import Mutation


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)
