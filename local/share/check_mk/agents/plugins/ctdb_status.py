#!/usr/bin/env python3
"""Checkmk agent plugin: CTDB cluster health and public IP allocation.

Runs `ctdb status` and `ctdb ip all` on whatever node this is installed on,
and emits two Checkmk sections:

    <<<ctdb_node_status:sep(0)>>>
    <<<ctdb_ip_allocation:sep(0)>>>

Each section is a single JSON line.

Both `ctdb status` and `ctdb ip all` return a CLUSTER-WIDE view regardless
of which node you run them on - that's intentional in CTDB. So this same script
is meant to be deployed identically toevery node in the cluster: each node reports 
its own "(THIS NODE)" row plus the same cluster-wide recovery mode and IP map every
other node sees. If one node's agent goes dark, the other nodes still carry the
full cluster picture.

Requires the `ctdb` CLI on PATH, reachable via its local control socket.
This typically requires root - if the Checkmk agent runs as an
unprivileged user on your system, you'll need a sudoers entry granting
passwordless `ctdb status` and `ctdb ip all` to that user.
See README.md for details.

If ctdb isn't installed, isn't running, or the call fails for any other
reason, this plugin does NOT crash silently. It emits an "error" key in
the section payload, and the check plugin on the Checkmk side turns that
into an UNKNOWN service rather than just losing the section.
"""

import configparser
import json
import re
import subprocess
from pathlib import Path

SECTION_NODE_STATUS = "ctdb_node_status"
SECTION_IP_ALLOCATION = "ctdb_ip_allocation"

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "ctdb_status.cfg"

DEFAULT_TIMEOUT_SECONDS = 15

NODE_LINE_RE = re.compile(
    r"^pnn:(?P<pnn>\d+)\s+(?P<ip>\S+)\s+(?P<state>\S+)"
    r"(?P<this_node>\s+\(THIS NODE\))?\s*$"
)

RECOVERY_LINE_RE = re.compile(r"^Recovery mode:\s*(?P<mode>\w+)")

IP_LINE_RE = re.compile(
    r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+(?P<pnn>-?\d+)\s*$"
)


def load_config():
    """Read ctdb_status.cfg if the Agent Bakery deployed one, else defaults."""
    cfg = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE, encoding="utf-8")
    section = cfg["ctdb_status"] if "ctdb_status" in cfg else {}
    return {
        "timeout": int(section.get("timeout", DEFAULT_TIMEOUT_SECONDS)),
    }


def run_ctdb(args, timeout):
    """Run a ctdb subcommand. Returns (stdout, error_message)."""
    try:
        result = subprocess.run(
            ["ctdb"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None, "ctdb command not found. Is this a CTDB cluster node?"
    except subprocess.TimeoutExpired:
        return None, "ctdb {} timed out after {}s".format(
            " ".join(args), timeout
        )

    if result.returncode != 0:
        stderr = result.stderr.strip() or "no error output"
        return None, "ctdb {} failed (rc={}): {}".format(
            " ".join(args), result.returncode, stderr
        )

    return result.stdout, None


def parse_node_status(output):
    nodes = []
    recovery_mode = None

    for raw_line in output.splitlines():
        line = raw_line.strip()

        node_match = NODE_LINE_RE.match(line)
        if node_match:
            nodes.append(
                {
                    "pnn": int(node_match.group("pnn")),
                    "ip": node_match.group("ip"),
                    "state": node_match.group("state"),
                    "this_node": bool(node_match.group("this_node")),
                }
            )
            continue

        recovery_match = RECOVERY_LINE_RE.match(line)
        if recovery_match:
            recovery_mode = recovery_match.group("mode")

    return {"nodes": nodes, "recovery_mode": recovery_mode}


def parse_ip_allocation(output):
    ips = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        match = IP_LINE_RE.match(line)
        if match:
            pnn = int(match.group("pnn"))
            ips.append(
                {
                    "ip": match.group("ip"),
                    # -1 to means "not currently hosted anywhere"
                    "pnn": pnn if pnn >= 0 else None,
                }
            )

    return {"ips": ips}


def emit_section(name, payload):
    print("<<<{}:sep(0)>>>".format(name))
    print(json.dumps(payload))


def main():
    config = load_config()
    timeout = config["timeout"]

    status_output, status_error = run_ctdb(["status"], timeout)
    if status_error:
        emit_section(SECTION_NODE_STATUS, {"error": status_error})
    else:
        emit_section(SECTION_NODE_STATUS, parse_node_status(status_output))

    ip_output, ip_error = run_ctdb(["ip", "all"], timeout)
    if ip_error:
        emit_section(SECTION_IP_ALLOCATION, {"error": ip_error})
    else:
        emit_section(SECTION_IP_ALLOCATION, parse_ip_allocation(ip_output))


if __name__ == "__main__":
    main()