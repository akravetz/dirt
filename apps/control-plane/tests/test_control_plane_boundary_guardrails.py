from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from dirt_control.api import browser, gateway
from dirt_control.api.browser import (
    AssetResponse,
    CommandResponse,
    CurrentMetricResponse,
    DeviceResponse,
    GatewayCredentialRotateResponse,
    HealthResponse,
    LightSchedulesResponse,
    MetricHistoryResponse,
    SiteResponse,
    SyncStatusResponse,
    TentResponse,
    TentStateResponse,
    UserResponse,
)
from dirt_shared.cloud_contract import (
    AssetCompleteResponse,
    AssetFailureResponse,
    CapturePolicyResponse,
    CatalogRequest,
    CatalogResponse,
    CommandClaimResponse,
    CommandResultResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    LatestMetricsRequest,
    PruneAssetsResponse,
    RollupsRequest,
    SignUploadResponse,
    UpsertCountResponse,
)


def test_hosted_browser_routes_keep_response_models() -> None:
    routes = _route_response_models(browser.router)

    assert routes[("GET", "/api/health")] is HealthResponse
    assert routes[("POST", "/api/auth/login")] is UserResponse
    assert routes[("GET", "/api/auth/me")] is UserResponse
    assert routes[("GET", "/api/sites")] == list[SiteResponse]
    assert routes[("GET", "/api/tents")] == list[TentResponse]
    assert routes[("GET", "/api/tents/{tent_id}/state")] is TentStateResponse
    assert (
        routes[("GET", "/api/tents/{tent_id}/metrics/current")]
        == list[CurrentMetricResponse]
    )
    assert routes[("GET", "/api/tents/{tent_id}/metrics/history")] is (
        MetricHistoryResponse
    )
    assert routes[("GET", "/api/tents/{tent_id}/devices")] == list[DeviceResponse]
    assert routes[("GET", "/api/tents/{tent_id}/lights/schedules")] is (
        LightSchedulesResponse
    )
    assert routes[("GET", "/api/tents/{tent_id}/assets/latest")] == list[AssetResponse]
    assert routes[("GET", "/api/assets/{asset_id}/signed-url")] is AssetResponse
    assert routes[("GET", "/api/sync/status")] is SyncStatusResponse
    assert routes[("POST", "/api/commands")] is CommandResponse
    assert (
        routes[("POST", "/api/admin/gateway-credentials/{credential_id}/rotate")]
        is GatewayCredentialRotateResponse
    )
    assert routes[("POST", "/api/admin/assets/prune-expired")] is (PruneAssetsResponse)
    assert routes[("GET", "/api/commands/{command_id}")] is CommandResponse
    assert routes[("GET", "/api/commands")] == list[CommandResponse]


def test_hosted_gateway_routes_keep_shared_boundary_models() -> None:
    routes = _route_contracts(gateway.router)

    assert routes[("POST", "/api/gateway/v1/heartbeat")] == (
        HeartbeatRequest,
        HeartbeatResponse,
    )
    assert routes[("PUT", "/api/gateway/v1/catalog")] == (
        CatalogRequest,
        CatalogResponse,
    )
    assert routes[("PUT", "/api/gateway/v1/metrics/latest")] == (
        LatestMetricsRequest,
        UpsertCountResponse,
    )
    assert routes[("POST", "/api/gateway/v1/metrics/rollups")] == (
        RollupsRequest,
        UpsertCountResponse,
    )
    assert (
        routes[("GET", "/api/gateway/v1/cameras/{camera_device_id}/capture-policy")][1]
        is CapturePolicyResponse
    )
    assert (
        routes[("POST", "/api/gateway/v1/assets/sign-upload")][1] is SignUploadResponse
    )
    assert (
        routes[("POST", "/api/gateway/v1/assets/complete")][1] is AssetCompleteResponse
    )
    assert (
        routes[("POST", "/api/gateway/v1/assets/upload-failure")][1]
        is AssetFailureResponse
    )
    assert (
        routes[("POST", "/api/gateway/v1/assets/prune-expired")][1]
        is PruneAssetsResponse
    )
    assert routes[("POST", "/api/gateway/v1/commands/claim")][1] is CommandClaimResponse
    assert (
        routes[("POST", "/api/gateway/v1/commands/{command_id}/result")][1]
        is CommandResultResponse
    )


def test_gateway_catalog_rejects_omitted_device_liveness() -> None:
    with pytest.raises(ValidationError):
        CatalogRequest.model_validate(
            {
                "site": {"site_id": "homebox", "name": "Homebox"},
                "devices": [
                    {
                        "tent_id": "main",
                        "device_id": "env-main",
                        "name": "Env Main",
                    }
                ],
            }
        )


def _route_response_models(router) -> dict[tuple[str, str], object]:
    return {
        (_single_method(route), route.path): route.response_model
        for route in router.routes
        if isinstance(route, APIRoute)
    }


def _route_contracts(router) -> dict[tuple[str, str], tuple[object, object]]:
    contracts = {}
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        body_field = route.body_field
        request_model = (
            body_field.field_info.annotation if body_field is not None else None
        )
        contracts[(_single_method(route), route.path)] = (
            request_model,
            route.response_model,
        )
    return contracts


def _single_method(route: APIRoute) -> str:
    return sorted(route.methods)[0]
