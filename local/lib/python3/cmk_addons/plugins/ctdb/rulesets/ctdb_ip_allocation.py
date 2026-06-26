from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Integer,
    SingleChoice,
    SingleChoiceElement,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, HostCondition, Topic


def _state_choice(title: str, default: str) -> SingleChoice:
    return SingleChoice(
        title=Title(title),
        elements=[
            SingleChoiceElement(name="ok", title=Title("OK")),
            SingleChoiceElement(name="warn", title=Title("WARN")),
            SingleChoiceElement(name="crit", title=Title("CRIT")),
            SingleChoiceElement(name="unknown", title=Title("UNKNOWN")),
        ],
        prefill=DefaultValue(default),
    )


def _parameter_form_ctdb_ip_allocation() -> Dictionary:
    return Dictionary(
        title=Title("CTDB Public IP Allocation"),
        help_text=Help(
            "Severity for public service IPs that aren't currently hosted "
            "by any node, and for uneven distribution of IPs across the "
            "cluster."
        ),
        elements={
            "orphaned_ip_state": DictElement(
                parameter_form=_state_choice(
                    "State when a public IP has no owning node",
                    "crit",
                ),
                required=True,
            ),
            "max_ips_per_node_warn": DictElement(
                parameter_form=Integer(
                    title=Title("Max public IPs on a single node before flagging"),
                    help_text=Help(
                        "If more than this many public IPs end up on one node "
                        "(e.g. all of them piling onto one node after a string "
                        "of failovers), flag reduced failover headroom."
                    ),
                    prefill=DefaultValue(2),
                ),
                required=True,
            ),
            "imbalance_state": DictElement(
                parameter_form=_state_choice(
                    "State when IP concentration exceeds the threshold above",
                    "warn",
                ),
                required=True,
            ),
        },
    )


rule_spec_ctdb_ip_allocation = CheckParameters(
    name="ctdb_ip_allocation",
    title=Title("CTDB Public IP Allocation"),
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_ctdb_ip_allocation,
    condition=HostCondition(),
)