"""Read-only MCP tools over the zk-collector REST/JSON endpoints (MYK-408).

Each tool is a plain function closed over a :class:`ZkCollectorClient` so
FastMCP's generated schema only exposes the tool's own arguments — the
client (and its token) never appear in the schema or in responses.

Tools (all read-only):
- ``attendance_stats`` → GET /api/attendance/stats (Bearer auth)
- ``list_punches``     → GET /attendance/api/attendance
- ``list_devices``     → GET /attendance/api/devices
- ``list_employees``   → GET /api/employees/
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .client import ZkApiError, ZkCollectorClient

GROUP_BY_VALUES = ("employee", "department", "company")
PER_PAGE_MIN = 10
PER_PAGE_MAX = 200
EMPLOYEES_PER_PAGE_DEFAULT = 20
EMPLOYEES_PER_PAGE_MAX = 200

ToolFunction = Callable[..., Any]


def build_tools(client: ZkCollectorClient) -> dict[str, ToolFunction]:
    """Build the read-only tool set bound to ``client``."""

    def attendance_stats(
        start_date: str | None = None,
        end_date: str | None = None,
        employee_id: int | None = None,
        department: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        """Attendance KPIs (present, absent, late, punctuality %) with optional filters.

        Args:
            start_date: inclusive start (YYYY-MM-DD); defaults to current month.
            end_date: inclusive end (YYYY-MM-DD); defaults to today.
            employee_id: limit to one employee id.
            department: limit to one department name.
            group_by: 'employee' | 'department' | 'company' for grouped rows.
        """
        if group_by is not None and group_by not in GROUP_BY_VALUES:
            raise ZkApiError(
                f"group_by must be one of {GROUP_BY_VALUES} (got {group_by!r})"
            )
        params: dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if employee_id is not None:
            params["employee_id"] = employee_id
        if department:
            params["department"] = department
        if group_by:
            params["group_by"] = group_by
        result: dict[str, Any] = client.get("/api/attendance/stats", params=params)
        return result

    def list_punches(
        start_date: str | None = None,
        end_date: str | None = None,
        user_id: str | None = None,
        device_ip: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """Raw clock-in/out records from the collector buffer, paginated.

        Args:
            start_date: inclusive start (YYYY-MM-DD).
            end_date: inclusive end (YYYY-MM-DD).
            user_id: filter by device user id.
            device_ip: filter by device IP.
            page: page number (1-based).
            per_page: records per page (10-200).
        """
        page = max(1, page)
        per_page = min(max(PER_PAGE_MIN, per_page), PER_PAGE_MAX)
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if user_id:
            params["user_id"] = user_id
        if device_ip:
            params["device_ip"] = device_ip
        result: dict[str, Any] = client.get("/attendance/api/attendance", params=params)
        return result

    def list_devices() -> dict[str, Any]:
        """Enabled attendance devices known to the platform (id, name, ip)."""
        result: dict[str, Any] = client.get("/attendance/api/devices")
        return result

    def list_employees(
        status: str | None = None,
        department: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = EMPLOYEES_PER_PAGE_DEFAULT,
    ) -> dict[str, Any]:
        """Employee registry (colaboradores), paginated, with optional filters.

        Args:
            status: 'active' | 'inactive'.
            department: exact department name.
            search: free-text match on code, name, email or department.
            page: page number (1-based).
            per_page: records per page (1-200).
        """
        page = max(1, page)
        per_page = min(max(1, per_page), EMPLOYEES_PER_PAGE_MAX)
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        if department:
            params["department"] = department
        if search:
            params["search"] = search
        result: dict[str, Any] = client.get("/api/employees/", params=params)
        return result

    return {
        "attendance_stats": attendance_stats,
        "list_punches": list_punches,
        "list_devices": list_devices,
        "list_employees": list_employees,
    }
