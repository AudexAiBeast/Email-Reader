import strawberry

from app.graphql.queries import Query

# Query-only schema: no `mutation=` argument is ever passed, so no mutation
# type can exist in this API, structurally guaranteeing retrieval-only access.
schema = strawberry.Schema(query=Query)
