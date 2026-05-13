from __future__ import annotations

from inspect import signature
from typing import Any, get_type_hints

from pydantic import BaseModel

from dirt_gateway import protocols
from dirt_shared.cloud_assets import AssetUploadProjection
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetRetentionRequest,
    AssetSignUploadRequest,
    CatalogRequest,
    CatalogResponse,
    CommandClaimResponse,
    CommandResultRequest,
    CommandResultResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    LatestMetricsRequest,
    PruneAssetsResponse,
    RollupsRequest,
    SignUploadResponse,
    UpsertCountResponse,
)


def test_cloud_gateway_client_uses_dtos_for_owned_boundary_payloads() -> None:
    expected = {
        "send_heartbeat": {"payload": HeartbeatRequest, "return": HeartbeatResponse},
        "put_catalog": {"payload": CatalogRequest, "return": CatalogResponse},
        "put_latest_metrics": {
            "payload": LatestMetricsRequest,
            "return": UpsertCountResponse,
        },
        "post_rollups": {"payload": RollupsRequest, "return": UpsertCountResponse},
        "sign_upload": {
            "payload": AssetSignUploadRequest,
            "return": SignUploadResponse,
        },
        "complete_asset": {
            "payload": AssetCompleteRequest,
            "return": AssetCompleteResponse,
        },
        "report_asset_failure": {
            "payload": AssetFailureRequest,
            "return": AssetFailureResponse,
        },
        "prune_expired_assets": {
            "payload": AssetRetentionRequest,
            "return": PruneAssetsResponse,
        },
        "claim_commands": {"return": CommandClaimResponse},
        "report_command_result": {
            "payload": CommandResultRequest,
            "return": CommandResultResponse,
        },
    }

    for method_name, expected_types in expected.items():
        hints = _method_hints(protocols.CloudGatewayClient, method_name)
        for name, expected_type in expected_types.items():
            assert hints[name] is expected_type
            assert issubclass(expected_type, BaseModel)


def test_local_gateway_services_return_projection_dtos() -> None:
    expected_returns = {
        "collect_catalog": CatalogRequest,
        "collect_latest_metrics": LatestMetricsRequest,
        "collect_rollups": RollupsRequest,
        "latest_snapshot_asset": AssetUploadProjection | None,
    }

    for method_name, expected_return in expected_returns.items():
        hints = _method_hints(protocols.LocalGatewayServices, method_name)
        assert hints["return"] == expected_return


def test_protocol_methods_do_not_accept_generic_payload_parameters() -> None:
    for protocol, method_names in {
        protocols.CloudGatewayClient: (
            "send_heartbeat",
            "put_catalog",
            "put_latest_metrics",
            "post_rollups",
            "sign_upload",
            "complete_asset",
            "report_asset_failure",
            "prune_expired_assets",
            "report_command_result",
        ),
        protocols.LocalGatewayServices: (
            "collect_catalog",
            "collect_latest_metrics",
            "collect_rollups",
        ),
    }.items():
        for method_name in method_names:
            parameter = signature(getattr(protocol, method_name)).parameters.get(
                "payload"
            )
            if parameter is None:
                continue
            annotation = _method_hints(protocol, method_name)["payload"]
            assert annotation not in (dict[str, Any], Any)


def _method_hints(protocol: type, method_name: str) -> dict[str, object]:
    method = getattr(protocol, method_name)
    return get_type_hints(method)
