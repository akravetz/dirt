from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from dirt_control.api import browser, gateway
from dirt_control.api.browser import (
    AssetResponse,
    BreedingLogbookBootstrapResponse,
    BreedingLogbookPlantDetailResponse,
    BreedingLogbookPlantListResponse,
    BreedingLogbookPlantRowResponse,
    BreedingLogbookSeedLotDetailResponse,
    BreedingLogbookSeedLotListResponse,
    CommandResponse,
    CurrentMetricResponse,
    DeviceResponse,
    GatewayCredentialRotateResponse,
    HealthResponse,
    LightSchedulesResponse,
    MetricHistoryResponse,
    MetricPresentationMetricResponse,
    MetricPresentationResponse,
    PlantMetricHistoryCollectionResponse,
    PlantMetricHistoryResponse,
    PlantSummaryResponse,
    SiteResponse,
    SyncStatusResponse,
    TentResponse,
    TentStateResponse,
    UserResponse,
)
from dirt_control.api.browser_schemas.breeding_logbook import (
    BreedingBulkCreateSexTestsRequest,
    BreedingBulkResultSexTestsRequest,
    BreedingLogbookSexTestResponse,
    BreedingUpdateSexTestRequest,
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
    assert routes[("GET", "/api/tents/{source_tent_id}/state")] is TentStateResponse
    assert (
        routes[("GET", "/api/tents/{source_tent_id}/metrics/current")]
        == list[CurrentMetricResponse]
    )
    assert routes[("GET", "/api/tents/{source_tent_id}/metrics/history")] is (
        MetricHistoryResponse
    )
    assert routes[("GET", "/api/metrics/presentation")] is MetricPresentationResponse
    assert (
        routes[("GET", "/api/breeding-logbook/bootstrap")]
        is BreedingLogbookBootstrapResponse
    )
    assert (
        routes[("GET", "/api/breeding-logbook/plants")]
        is BreedingLogbookPlantListResponse
    )
    assert (
        routes[("GET", "/api/breeding-logbook/seed-lots")]
        is BreedingLogbookSeedLotListResponse
    )
    assert (
        routes[("GET", "/api/breeding-logbook/seed-lots/{seed_lot_id}")]
        is BreedingLogbookSeedLotDetailResponse
    )
    assert (
        routes[("GET", "/api/breeding-logbook/plants/{plant_key}/metrics/history")]
        is PlantMetricHistoryResponse
    )
    assert (
        routes[("GET", "/api/breeding-logbook/plants/{plant_key}")]
        is BreedingLogbookPlantDetailResponse
    )
    assert routes[("POST", "/api/breeding-logbook/seed-lots")] is CommandResponse
    assert (
        routes[("POST", "/api/breeding-logbook/seed-lots/{seed_lot_id}:update")]
        is CommandResponse
    )
    assert routes[("POST", "/api/breeding-logbook/plants:germinate")] is CommandResponse
    assert routes[("POST", "/api/breeding-logbook/plants:clone")] is CommandResponse
    assert routes[("POST", "/api/breeding-logbook/plants:bulk-sex")] is CommandResponse
    assert routes[("POST", "/api/breeding-logbook/plants:bulk-move")] is CommandResponse
    assert (
        routes[("POST", "/api/breeding-logbook/plants:update-facts")] is CommandResponse
    )
    assert (
        routes[("POST", "/api/breeding-logbook/sex-tests:bulk-create")]
        is CommandResponse
    )
    assert (
        routes[("POST", "/api/breeding-logbook/sex-tests/{sex_test_id}:update")]
        is CommandResponse
    )
    assert (
        routes[("POST", "/api/breeding-logbook/sex-tests:bulk-result")]
        is CommandResponse
    )
    assert routes[("POST", "/api/breeding-logbook/plants:bulk-cull")] is CommandResponse
    assert routes[("POST", "/api/breeding-logbook/plants:bulk-note")] is CommandResponse
    assert (
        routes[("POST", "/api/breeding-logbook/plants/{plant_key}/notes")]
        is CommandResponse
    )
    assert (
        routes[("GET", "/api/tents/{source_tent_id}/plants")]
        == list[PlantSummaryResponse]
    )
    assert (
        routes[("GET", "/api/tents/{source_tent_id}/plants/metrics/history")]
        is PlantMetricHistoryCollectionResponse
    )
    assert (
        routes[("GET", "/api/tents/{source_tent_id}/devices")] == list[DeviceResponse]
    )
    assert routes[("GET", "/api/tents/{source_tent_id}/lights/schedules")] is (
        LightSchedulesResponse
    )
    assert (
        routes[("GET", "/api/tents/{source_tent_id}/assets/latest")]
        == list[AssetResponse]
    )
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


def test_hosted_browser_sex_test_routes_keep_request_models() -> None:
    routes = _route_contracts(browser.router)

    assert routes[("POST", "/api/breeding-logbook/sex-tests:bulk-create")] == (
        BreedingBulkCreateSexTestsRequest,
        CommandResponse,
    )
    assert routes[("POST", "/api/breeding-logbook/sex-tests/{sex_test_id}:update")] == (
        BreedingUpdateSexTestRequest,
        CommandResponse,
    )
    assert routes[("POST", "/api/breeding-logbook/sex-tests:bulk-result")] == (
        BreedingBulkResultSexTestsRequest,
        CommandResponse,
    )


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
                "site_id": "homebox",
                "site": {"source_site_id": 1, "name": "Homebox"},
                "sex_tests": [],
                "devices": [
                    {
                        "source_tent_id": 1,
                        "source_zone_id": None,
                        "device_id": "env-main",
                        "name": "Env Main",
                    }
                ],
            }
        )


def test_metric_presentation_metric_response_requires_owned_contract_shape() -> None:
    payload = {
        "metric": "temperature_f",
        "display_name": "Temperature",
        "unit": "F",
        "accent": "temp",
        "value_precision": 1,
        "y_min": None,
        "y_max": None,
        "display_order": 10,
    }

    assert MetricPresentationMetricResponse.model_validate(payload).y_min is None

    missing_required_nullable = dict(payload)
    del missing_required_nullable["y_min"]
    with pytest.raises(ValidationError):
        MetricPresentationMetricResponse.model_validate(missing_required_nullable)

    with pytest.raises(ValidationError):
        MetricPresentationMetricResponse.model_validate(
            {**payload, "unexpected_unit": "%"}
        )

    with pytest.raises(ValidationError):
        MetricPresentationMetricResponse.model_validate(
            {**payload, "accent": "invented"}
        )


def test_breeding_logbook_plant_row_requires_owned_contract_shape() -> None:
    payload = {
        "id": "1",
        "key": "SBBS-R1-001",
        "name": "Plant A",
        "strain": "Sugar Black Rose",
        "generation": "R1",
        "parents_label": "Sugar Black Rose x Black Sugar",
        "sex_key": "female",
        "stage_key": "flower",
        "stage_day": 44,
        "is_clone": False,
        "germinated_at": "2026-03-17T12:00:00Z",
        "germinated_on": "2026-03-17",
        "taken_at": None,
        "taken_on": None,
        "rooted_at": None,
        "rooted_on": None,
        "veg_started_at": "2026-04-02T12:00:00Z",
        "veg_started_on": "2026-04-02",
        "flower_started_at": "2026-05-04T12:00:00Z",
        "flower_started_on": "2026-05-04",
        "culled_at": None,
        "culled_on": None,
        "culled_reason": None,
        "harvested_at": None,
        "harvested_on": None,
        "selected_for_breeding_at": None,
        "selected_for_breeding_on": None,
        "selected_for_breeding_reason": None,
        "current_tent_id": 1,
        "current_tent_name": "Main Tent",
        "grid_position": "A1",
        "seed_lot_label": "SBBS R1 #1",
        "last_note": "",
        "telemetry_summary": "1 plant stream",
        "sex_tests": [],
    }

    assert BreedingLogbookPlantRowResponse.model_validate(payload).culled_on is None

    missing_required_nullable = dict(payload)
    del missing_required_nullable["selected_for_breeding_reason"]
    with pytest.raises(ValidationError):
        BreedingLogbookPlantRowResponse.model_validate(missing_required_nullable)

    with pytest.raises(ValidationError):
        BreedingLogbookPlantRowResponse.model_validate(
            {**payload, "unexpected_unit": "%"}
        )


def test_breeding_logbook_sex_test_response_requires_owned_contract_shape() -> None:
    payload = {
        "id": "1000",
        "source_sex_test_id": 1000,
        "source_plant_id": 1,
        "vendor_name": "Farmer Freeman",
        "assay_name": "EZ-XY",
        "vendor_test_code": "FF-001",
        "sample_collected_at": "2026-07-01T12:00:00Z",
        "sample_sent_at": None,
        "result_received_at": None,
        "result_sex_key": None,
        "is_inconclusive": False,
        "notes": None,
    }

    assert BreedingLogbookSexTestResponse.model_validate(payload).notes is None

    missing_required_nullable = dict(payload)
    del missing_required_nullable["result_received_at"]
    with pytest.raises(ValidationError):
        BreedingLogbookSexTestResponse.model_validate(missing_required_nullable)

    with pytest.raises(ValidationError):
        BreedingLogbookSexTestResponse.model_validate(
            {**payload, "unexpected_unit": "%"}
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
