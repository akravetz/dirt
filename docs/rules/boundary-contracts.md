# Boundary Contract Rule

Read this before changing any payload that crosses a process, network, persistence, or generated-client boundary.

## Rule

Dirt uses Pydantic models as the single schema enforcement mechanism at codebase boundaries.

Use Pydantic `BaseModel` DTOs for:

- FastAPI request bodies and JSON responses.
- Gateway-to-control-plane request and response payloads.
- Cloud outbox event payloads.
- Command claim, command result, and actuator command payloads.
- Structured payloads persisted as JSON where later code depends on the shape.

Use SQLModel table models for database rows. SQLAlchemy is the implementation substrate underneath SQLModel and is acceptable for column types, constraints, indexes, query expressions, and rare data-layer escape hatches, but do not introduce parallel SQLAlchemy declarative row models. Do not use database models as public wire contracts unless the row type is deliberately the API contract. Storage shape and wire shape should be allowed to evolve independently.

Use plain dataclasses for internal pure-Python value objects only when they do not cross a boundary and do not need runtime validation or JSON Schema.

Use `dict[str, Any]` only for truly opaque third-party payloads, unstructured metadata, or adapter code that immediately validates into or serializes out of a Pydantic model.

## Boundary Checklist

When adding or editing a boundary payload:

1. Define or update a Pydantic DTO in the canonical contract module for that boundary.
2. For required-but-nullable fields, use an explicit required field whose type includes `None`; do not make the key optional by giving it a default.
3. Prefer `ConfigDict(extra="forbid")` for owned protocols so misspelled or stale fields fail loudly.
4. Construct DTO instances at the producer before enqueueing, storing, or sending.
5. Store outbox JSON with `model_dump(mode="json")`.
6. Validate inbound JSON from HTTP clients, command claim responses, and persisted outbox rows with `model_validate()` or `model_validate_json()`.
7. Put the same DTO on the FastAPI route as the request body or `response_model` when the route exposes that shape.
8. Add a focused regression test that would fail if a required field is omitted.

## Current Priority Areas

The local `dirt-web` API is mostly already covered by FastAPI `response_model` contracts and generated OpenAPI clients. The highest-risk gap is the hosted gateway sync path:

- `apps/gateway/src/dirt_gateway/protocols.py`
- `apps/gateway/src/dirt_gateway/local.py`
- `apps/gateway/src/dirt_gateway/sync.py`
- `apps/gateway/src/dirt_gateway/cloud.py`
- `apps/gateway/src/dirt_gateway/commands.py`
- `apps/control-plane/src/dirt_control/api/gateway.py`
- `apps/control-plane/src/dirt_control/api/browser.py`

Do not add new raw gateway payload dictionaries in these files. If a temporary raw dictionary is unavoidable during migration, validate it at the nearest boundary and add a TODO that points to `docs/epics/typed-boundary-contracts/ExecPlan.md`.

## Why This Exists

A hosted dashboard bug showed `last seen never` for an actively reporting breeding-tent ESP32 because local `device.last_seen` existed, metric sync worked, but the raw gateway catalog dictionary omitted `last_seen_at`. The cloud API accepted the missing key because the field had a default of `None`, and the frontend rendered the null value. A typed producer-side DTO with a required nullable `last_seen_at` key would have failed before the payload reached the outbox.

## References

- Pydantic models: https://docs.pydantic.dev/latest/concepts/models/
- FastAPI response models: https://fastapi.tiangolo.com/tutorial/response-model/
- ExecPlan: `docs/epics/typed-boundary-contracts/ExecPlan.md`
