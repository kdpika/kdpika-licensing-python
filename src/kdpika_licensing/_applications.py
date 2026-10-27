"""Signed desktop/web entitlement checks; a declaration is not attestation."""
from typing import Any

def application_allowed(payload: dict[str, Any], application_type: str) -> bool:
    features = payload.get("features")
    feature_scope = features.get("application_access", "both") if isinstance(features, dict) else "both"
    scope = payload.get("application_access", feature_scope)
    bound = payload.get("application_type")
    return (application_type in ("desktop", "web") and scope in ("both", "desktop", "web")
            and (scope == "both" or scope == application_type)
            and (bound == application_type if bound is not None else scope == "both"))
