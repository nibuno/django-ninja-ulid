"""Existing Ninja alias behavior retained as test fixtures, without a fix."""

def _observe(schema, payload, operations, namespace):
    from django.test import Client, override_settings
    from django.urls import path
    from ninja import NinjaAPI

    api = NinjaAPI(urls_namespace=namespace)

    def view(request):
        return payload.copy()

    for route, by_alias in operations:
        api.get(
            f"/{route}", response=schema, by_alias=by_alias,
            operation_id=f"{namespace}_{route}",
        )(view)

    class Urlconf:
        urlpatterns = [path("alias-probe/", api.urls)]

    responses = {}
    with override_settings(ROOT_URLCONF=Urlconf):
        client = Client()
        for route, _ in operations:
            response = client.get(f"/alias-probe/{route}")
            responses[route] = {"status": response.status_code, "body": response.json()}
        spec = api.get_openapi_schema()

    refs = {
        route: spec["paths"][f"/alias-probe/{route}"]["get"]["responses"][200]
        ["content"]["application/json"]["schema"]["$ref"]
        for route, _ in operations
    }
    definitions = {
        ref.rsplit("/", 1)[1]: spec["components"]["schemas"][ref.rsplit("/", 1)[1]]
        for ref in refs.values()
    }
    return {
        "registration_order": [{"route": route, "by_alias": flag} for route, flag in operations],
        "responses": responses,
        "openapi_response_refs": refs,
        "components": definitions,
        "documented_properties": {
            route: list(definitions[ref.rsplit("/", 1)[1]]["properties"])
            for route, ref in refs.items()
        },
    }


def observe_mixed_aliases(order):
    from ninja import Schema
    from pydantic import Field

    class SharedAliasResponse(Schema):
        owner: str = Field(..., alias="owner_id")

    operations = [("aliased" if flag else "plain", flag) for flag in order]
    return _observe(
        SharedAliasResponse, {"owner_id": "example"}, operations,
        f"mixed-alias-{int(order[0])}-{int(order[1])}",
    )


def observe_serialization_alias():
    """The single-response-mode example reported in upstream issue #1328."""
    from ninja import Schema
    from pydantic import Field

    class SerializationAliasResponse(Schema):
        foo: str = Field(..., alias="alias1")
        bar: str = Field(..., serialization_alias="alias2")

    return _observe(
        SerializationAliasResponse, {"alias1": "foo", "bar": "bar"},
        [("aliased", True)], "serialization-alias-probe",
    )
