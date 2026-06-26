"""CTDB Cluster Health check plugin.

Consumes the <<<ctdb_node_status>>> agent section (emitted by
agents/linux/plugins/ctdb_status.py) and produces a single "CTDB Cluster
Health" service per host covering:

  - This node's own CTDB-reported health (OK / PARTIALLYONLINE / DISABLED /
    STOPPED / UNHEALTHY / DISCONNECTED / BANNED) - distinct from "is the
    ctdbd process running", which is already covered elsewhere.
  - Cluster-wide recovery mode (NORMAL / RECOVERY), with a grace period
    before a stuck RECOVERY is treated as an actual problem rather than a
    normal brief failover blip.

Deploy identically to every node in the cluster - this is meant to be
repeated across the active/active set, not piggybacked onto one host.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional
import json
import time

from cmk.agent_based.v2 import (
    AgentSection,
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    Metric,
    Result,
    Service,
    State,
    StringTable,
    get_value_store,
)


@dataclass
class NodeStatusEntry:
    pnn: int
    ip: str
    state: str
    this_node: bool


@dataclass
class SectionCtdbNodeStatus:
    nodes: list[NodeStatusEntry]
    recovery_mode: Optional[str]
    error: Optional[str] = None


# Maps the node states the agent plugin can report onto the check
# parameter key that controls severity for that state. OK has no entry -
# it's always OK. Any state not in this map (shouldn't happen against a
# real cluster, but CTDB has shown new states across versions) falls back
# to UNKNOWN rather than silently passing as OK.
NODE_STATE_PARAM_KEYS = {
    "PARTIALLYONLINE": "partiallyonline_state",
    "DISABLED": "disabled_state",
    "STOPPED": "stopped_state",
    "UNHEALTHY": "unhealthy_state",
    "DISCONNECTED": "disconnected_state",
    "BANNED": "banned_state",
}

DEFAULT_NODE_STATUS_PARAMS: Mapping[str, Any] = {
    "partiallyonline_state": "warn",
    "disabled_state": "warn",
    "stopped_state": "warn",
    "unhealthy_state": "crit",
    "disconnected_state": "crit",
    "banned_state": "crit",
    "recovery_grace_period": 30,
    "recovery_stuck_state": "crit",
}


def _state_from_param(value: str) -> State:
    return {
        "ok": State.OK,
        "warn": State.WARN,
        "crit": State.CRIT,
        "unknown": State.UNKNOWN,
    }[value]


def parse_ctdb_node_status(string_table: StringTable) -> SectionCtdbNodeStatus:
    if not string_table:
        return SectionCtdbNodeStatus(
            nodes=[], recovery_mode=None, error="No data received from agent plugin"
        )

    raw = json.loads(string_table[0][0])

    if "error" in raw:
        return SectionCtdbNodeStatus(nodes=[], recovery_mode=None, error=raw["error"])

    nodes = [NodeStatusEntry(**entry) for entry in raw.get("nodes", [])]
    return SectionCtdbNodeStatus(
        nodes=nodes, recovery_mode=raw.get("recovery_mode"), error=None
    )


def discover_ctdb_node_status(section: SectionCtdbNodeStatus) -> DiscoveryResult:
    if section.error:
        return
    if not section.nodes and section.recovery_mode is None:
        return
    yield Service()


def _check_node_health(
    params: Mapping[str, Any], section: SectionCtdbNodeStatus
) -> CheckResult:
    own_node = next((n for n in section.nodes if n.this_node), None)
    other_nodes = [n for n in section.nodes if not n.this_node]
    other_summary = (
        ", ".join(f"pnn{n.pnn}={n.state}" for n in other_nodes)
        if other_nodes
        else "none"
    )

    if own_node is None:
        yield Result(
            state=State.UNKNOWN,
            summary="Could not identify local node in ctdb status output",
            details=f"Other nodes seen from here: {other_summary}",
        )
        return

    node_state = own_node.state.upper()

    if node_state == "OK":
        state = State.OK
    else:
        param_key = NODE_STATE_PARAM_KEYS.get(node_state)
        state = _state_from_param(params[param_key]) if param_key else State.UNKNOWN

    yield Result(
        state=state,
        summary=f"Node health: {node_state}",
        details=(
            f"This node: pnn {own_node.pnn} ({own_node.ip}), state {node_state}. "
            f"Other nodes seen from here: {other_summary}"
        ),
    )


def _check_recovery_mode(
    params: Mapping[str, Any], section: SectionCtdbNodeStatus
) -> CheckResult:
    value_store = get_value_store()

    if section.recovery_mode is None:
        yield Result(state=State.UNKNOWN, summary="Recovery mode: unknown")
        return

    mode = section.recovery_mode.upper()

    if mode == "NORMAL":
        value_store.pop("recovery_since", None)
        yield Result(state=State.OK, summary="Recovery mode: NORMAL")
        yield Metric("ctdb_recovery_elapsed", 0.0)
        return

    now = time.time()
    started = value_store.get("recovery_since")
    if started is None:
        started = now
        value_store["recovery_since"] = started

    elapsed = now - started
    grace = params["recovery_grace_period"]

    yield Metric("ctdb_recovery_elapsed", elapsed)

    if elapsed < grace:
        yield Result(
            state=State.WARN,
            summary=f"Recovery mode: {mode} ({elapsed:.0f}s, grace period {grace}s)",
        )
    else:
        state = _state_from_param(params["recovery_stuck_state"])
        yield Result(
            state=state,
            summary=(
                f"Recovery mode: {mode} stuck for {elapsed:.0f}s "
                f"(grace period {grace}s exceeded)"
            ),
        )


def check_ctdb_node_status(
    params: Mapping[str, Any], section: SectionCtdbNodeStatus
) -> CheckResult:
    if section.error:
        yield Result(state=State.UNKNOWN, summary=f"CTDB error: {section.error}")
        return

    yield from _check_node_health(params, section)
    yield from _check_recovery_mode(params, section)


agent_section_ctdb_node_status = AgentSection(
    name="ctdb_node_status",
    parse_function=parse_ctdb_node_status,
)

check_plugin_ctdb_node_status = CheckPlugin(
    name="ctdb_node_status",
    service_name="CTDB Cluster Health",
    discovery_function=discover_ctdb_node_status,
    check_function=check_ctdb_node_status,
    check_default_parameters=DEFAULT_NODE_STATUS_PARAMS,
    check_ruleset_name="ctdb_cluster_health",
)