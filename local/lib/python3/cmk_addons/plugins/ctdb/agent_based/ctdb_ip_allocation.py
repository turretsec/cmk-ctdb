"""CTDB Public IP Allocation check plugin.

Consumes the <<<ctdb_ip_allocation>>> agent section (emitted by
agents/linux/plugins/ctdb_status.py) and produces a single "CTDB Public IP
Allocation" service per host, reporting:

  - Any public service IP with no owning node right now (a live outage at
    that address, regardless of how the rest of the cluster looks).
  - Uneven distribution - e.g. all public IPs piling onto one node after a
    string of failovers, which still serves traffic fine but has lost its
    failover headroom.

Deploy identically to every node in the cluster, same as ctdb_node_status -
`ctdb ip all` returns the same cluster-wide map regardless of which node
you ask, so this is intentionally duplicated for resilience.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional
import json

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Result,
    Service,
    State,
    StringTable,
)


@dataclass
class IpAllocationEntry:
    ip: str
    pnn: Optional[int]


@dataclass
class SectionCtdbIpAllocation:
    ips: list[IpAllocationEntry]
    error: Optional[str] = None


DEFAULT_IP_ALLOCATION_PARAMS: Mapping[str, Any] = {
    "orphaned_ip_state": "crit",
    "max_ips_per_node_warn": 2,
    "imbalance_state": "warn",
}


def _state_from_param(value: str) -> State:
    return {
        "ok": State.OK,
        "warn": State.WARN,
        "crit": State.CRIT,
        "unknown": State.UNKNOWN,
    }[value]


def parse_ctdb_ip_allocation(string_table: StringTable) -> SectionCtdbIpAllocation:
    if not string_table:
        return SectionCtdbIpAllocation(
            ips=[], error="No data received from agent plugin"
        )

    raw = json.loads(string_table[0][0])

    if "error" in raw:
        return SectionCtdbIpAllocation(ips=[], error=raw["error"])

    ips = [IpAllocationEntry(**entry) for entry in raw.get("ips", [])]
    return SectionCtdbIpAllocation(ips=ips, error=None)


def discover_ctdb_ip_allocation(section: SectionCtdbIpAllocation) -> DiscoveryResult:
    if section.error or not section.ips:
        return
    yield Service()


def check_ctdb_ip_allocation(
    params: Mapping[str, Any], section: SectionCtdbIpAllocation
) -> CheckResult:
    if section.error:
        yield Result(state=State.UNKNOWN, summary=f"CTDB error: {section.error}")
        return

    if not section.ips:
        yield Result(state=State.UNKNOWN, summary="No public IPs reported")
        return

    orphaned = [ip for ip in section.ips if ip.pnn is None]

    counts: dict[int, int] = {}
    for ip in section.ips:
        if ip.pnn is not None:
            counts[ip.pnn] = counts.get(ip.pnn, 0) + 1

    distribution = (
        ", ".join(f"pnn{pnn}={count}" for pnn, count in sorted(counts.items()))
        or "none hosted"
    )

    yield Result(
        state=State.OK,
        summary=f"{len(section.ips)} public IP(s) tracked",
        details=f"Distribution: {distribution}",
    )

    if orphaned:
        orphan_list = ", ".join(ip.ip for ip in orphaned)
        yield Result(
            state=_state_from_param(params["orphaned_ip_state"]),
            summary=f"{len(orphaned)} unhosted: {orphan_list}",
        )

    if counts:
        max_on_one_node = max(counts.values())
        warn_threshold = params["max_ips_per_node_warn"]
        if max_on_one_node > warn_threshold:
            worst_pnn = max(counts, key=counts.get)
            yield Result(
                state=_state_from_param(params["imbalance_state"]),
                summary=(
                    f"{max_on_one_node} IPs concentrated on pnn {worst_pnn} "
                    f"(threshold {warn_threshold})"
                ),
            )


agent_section_ctdb_ip_allocation = AgentSection(
    name="ctdb_ip_allocation",
    parse_function=parse_ctdb_ip_allocation,
)

check_plugin_ctdb_ip_allocation = CheckPlugin(
    name="ctdb_ip_allocation",
    service_name="CTDB Public IP Allocation",
    discovery_function=discover_ctdb_ip_allocation,
    check_function=check_ctdb_ip_allocation,
    check_default_parameters=DEFAULT_IP_ALLOCATION_PARAMS,
    check_ruleset_name="ctdb_ip_allocation",
)