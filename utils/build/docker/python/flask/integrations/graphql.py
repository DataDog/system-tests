import graphene
from graphql import GraphQLError
from graphene import Schema

users = [
    {"id": 1, "name": "foo"},
    {"id": 2, "name": "bar"},
    {"id": 3, "name": "bar"},
]


class User(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()


class Extension(graphene.ObjectType):
    key = graphene.String()
    value = graphene.String()


class Error(graphene.ObjectType):
    message = graphene.String()
    extensions = graphene.List(Extension)


class Query(graphene.ObjectType):
    user = graphene.Field(User, id=graphene.Int(required=True))
    user_by_name = graphene.List(User, name=graphene.String())
    test_injection = graphene.List(User, path=graphene.String())
    with_error = graphene.ID()

    def resolve_user(self, info, id):
        return next((user for user in users if user["id"] == id), None)

    def resolve_user_by_name(self, info, name=None):
        return [user for user in users if user["name"] == name]

    def resolve_test_injection(self, info, path=None):
        if path:
            try:
                with open(path, "r") as file:
                    pass
            except FileNotFoundError:
                pass
        return users

    def resolve_with_error(self, info):
        raise GraphQLError(
            message="test error",
            extensions={
                "int": 1,
                "float": 1.1,
                "str": "1",
                "bool": True,
                "other": [1, "foo"],
                "not_captured": "foo",
            },
        )
