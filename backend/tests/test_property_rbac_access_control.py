"""Property-based test for RBAC access control enforcement.

Feature: crisislink-emergency-ai-copilot, Property 12: RBAC Access Control Enforcement

Validates: Requirements 10.3

Uses Hypothesis to generate random (user_role, data_path, operation) triples
and verify Firebase Security Rules grant/deny access correctly per role
definitions:
- Operators: access call data and dispatch actions
- Responders: access their own unit data and dispatch details
- Admins: access analytics and all unit data
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from integration.security import Operation, UserRole, check_access


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid roles
role_strategy = st.sampled_from([r.value for r in UserRole])

# Valid operations
operation_strategy = st.sampled_from([o.value for o in Operation])

# Generate realistic RTDB path segments
_id_chars = st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_")
_resource_id = st.text(min_size=1, max_size=20, alphabet=_id_chars)

# Call sub-paths that appear under /calls/{call_id}/
_call_subpaths = st.sampled_from([
    "transcript",
    "classification",
    "caller_state",
    "dispatch_card",
    "confirmed_unit",
    "guidance",
    "manual_override",
    "started_at",
    "updated_at",
])

# Unit sub-paths that appear under /units/{unit_id}/
_unit_subpaths = st.sampled_from([
    "status",
    "location",
    "type",
    "hospital_or_station",
    "capabilities",
    "last_updated",
])

# Analytics sub-paths
_analytics_subpaths = st.sampled_from([
    "response_times",
    "classification_accuracy",
    "unit_utilization",
    "incident_heatmap",
    "trend_reports",
])

# Full path strategies for each top-level collection
calls_path_strategy = st.one_of(
    st.just("/calls"),
    _resource_id.map(lambda cid: f"/calls/{cid}"),
    st.tuples(_resource_id, _call_subpaths).map(
        lambda t: f"/calls/{t[0]}/{t[1]}"
    ),
)

units_path_strategy = st.one_of(
    st.just("/units"),
    _resource_id.map(lambda uid: f"/units/{uid}"),
    st.tuples(_resource_id, _unit_subpaths).map(
        lambda t: f"/units/{t[0]}/{t[1]}"
    ),
)

analytics_path_strategy = st.one_of(
    st.just("/analytics"),
    _resource_id.map(lambda aid: f"/analytics/{aid}"),
    st.tuples(_resource_id, _analytics_subpaths).map(
        lambda t: f"/analytics/{t[0]}/{t[1]}"
    ),
)

# Combined path strategy covering all collections
any_path_strategy = st.one_of(
    calls_path_strategy,
    units_path_strategy,
    analytics_path_strategy,
)


# ---------------------------------------------------------------------------
# Property 12: RBAC Access Control Enforcement
# ---------------------------------------------------------------------------


class TestRBACAccessControlEnforcement:
    """Property 12: RBAC Access Control Enforcement

    For any (user_role, data_path, operation) triple, the Firebase Security
    Rules SHALL grant access if and only if the role is authorized for that
    path and operation: operators access call data and dispatch actions;
    responders access their own unit data and dispatch details; admins access
    analytics and all unit data. Unauthorized combinations SHALL be denied.

    **Validates: Requirements 10.3**
    """

    # ---------------------------------------------------------------
    # Operator role properties
    # ---------------------------------------------------------------

    @given(path=calls_path_strategy, operation=operation_strategy)
    @settings(max_examples=200)
    def test_operator_can_access_call_data(self, path: str, operation: str):
        """Operators can read and write all call data paths.

        **Validates: Requirements 10.3**
        """
        assert check_access("operator", path, operation) is True

    @given(path=units_path_strategy)
    @settings(max_examples=200)
    def test_operator_can_read_unit_data(self, path: str):
        """Operators can read unit data for dispatch decisions.

        **Validates: Requirements 10.3**
        """
        assert check_access("operator", path, "read") is True

    @given(path=units_path_strategy)
    @settings(max_examples=200)
    def test_operator_cannot_write_unit_data(self, path: str):
        """Operators cannot write to unit data directly.

        **Validates: Requirements 10.3**
        """
        assert check_access("operator", path, "write") is False

    @given(path=analytics_path_strategy, operation=operation_strategy)
    @settings(max_examples=200)
    def test_operator_cannot_access_analytics(self, path: str, operation: str):
        """Operators have no access to analytics paths.

        **Validates: Requirements 10.3**
        """
        assert check_access("operator", path, operation) is False

    # ---------------------------------------------------------------
    # Responder role properties
    # ---------------------------------------------------------------

    @given(path=units_path_strategy, operation=operation_strategy)
    @settings(max_examples=200)
    def test_responder_can_access_unit_data(self, path: str, operation: str):
        """Responders can read and write their own unit data.

        **Validates: Requirements 10.3**
        """
        assert check_access("responder", path, operation) is True

    @given(path=calls_path_strategy)
    @settings(max_examples=200)
    def test_responder_can_read_call_data(self, path: str):
        """Responders can read dispatch details from call data.

        **Validates: Requirements 10.3**
        """
        assert check_access("responder", path, "read") is True

    @given(path=calls_path_strategy)
    @settings(max_examples=200)
    def test_responder_cannot_write_call_data(self, path: str):
        """Responders cannot write to call data.

        **Validates: Requirements 10.3**
        """
        assert check_access("responder", path, "write") is False

    @given(path=analytics_path_strategy, operation=operation_strategy)
    @settings(max_examples=200)
    def test_responder_cannot_access_analytics(self, path: str, operation: str):
        """Responders have no access to analytics paths.

        **Validates: Requirements 10.3**
        """
        assert check_access("responder", path, operation) is False

    # ---------------------------------------------------------------
    # Admin role properties
    # ---------------------------------------------------------------

    @given(path=any_path_strategy)
    @settings(max_examples=200)
    def test_admin_can_read_everything(self, path: str):
        """Admins have full read access to all paths.

        **Validates: Requirements 10.3**
        """
        assert check_access("admin", path, "read") is True

    @given(path=analytics_path_strategy)
    @settings(max_examples=200)
    def test_admin_can_write_analytics(self, path: str):
        """Admins can write to analytics paths.

        **Validates: Requirements 10.3**
        """
        assert check_access("admin", path, "write") is True

    @given(path=calls_path_strategy)
    @settings(max_examples=200)
    def test_admin_cannot_write_call_data(self, path: str):
        """Admins cannot write to call data directly.

        **Validates: Requirements 10.3**
        """
        assert check_access("admin", path, "write") is False

    @given(path=units_path_strategy)
    @settings(max_examples=200)
    def test_admin_cannot_write_unit_data(self, path: str):
        """Admins cannot write to unit data directly.

        **Validates: Requirements 10.3**
        """
        assert check_access("admin", path, "write") is False

    # ---------------------------------------------------------------
    # Cross-cutting: unknown roles and operations are denied
    # ---------------------------------------------------------------

    @given(
        path=any_path_strategy,
        operation=operation_strategy,
    )
    @settings(max_examples=200)
    def test_unknown_role_is_denied(self, path: str, operation: str):
        """An unrecognised role is always denied access.

        **Validates: Requirements 10.3**
        """
        assert check_access("unknown_role", path, operation) is False

    @given(
        role=role_strategy,
        path=any_path_strategy,
    )
    @settings(max_examples=200)
    def test_unknown_operation_is_denied(self, role: str, path: str):
        """An unrecognised operation is always denied.

        **Validates: Requirements 10.3**
        """
        assert check_access(role, path, "delete") is False

    @given(
        role=role_strategy,
        operation=operation_strategy,
    )
    @settings(max_examples=200)
    def test_empty_path_is_denied(self, role: str, operation: str):
        """An empty path is always denied.

        **Validates: Requirements 10.3**
        """
        assert check_access(role, "", operation) is False
