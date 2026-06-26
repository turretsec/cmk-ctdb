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


def _parameter_form_ctdb_cluster_health() -> Dictionary:
    return Dictionary(
        title=Title("CTDB Cluster Health"),
        help_text=Help(
            "Severity for this node's CTDB-reported health state (distinct "
            "from whether the ctdbd process is merely running) and for how "
            "long the cluster may sit in RECOVERY mode before it's treated "
            "as stuck rather than a normal brief failover."
        ),
        elements={
            "partiallyonline_state": DictElement(
                parameter_form=_state_choice(
                    "State for PARTIALLYONLINE "
                    "(some interfaces down, node still serving)",
                    "warn",
                ),
                required=True,
            ),
            "disabled_state": DictElement(
                parameter_form=_state_choice(
                    "State for DISABLED (administratively pulled from rotation)",
                    "warn",
                ),
                required=True,
            ),
            "stopped_state": DictElement(
                parameter_form=_state_choice(
                    "State for STOPPED (administratively removed from cluster)",
                    "warn",
                ),
                required=True,
            ),
            "unhealthy_state": DictElement(
                parameter_form=_state_choice(
                    "State for UNHEALTHY (a monitored service is actually broken)",
                    "crit",
                ),
                required=True,
            ),
            "disconnected_state": DictElement(
                parameter_form=_state_choice(
                    "State for DISCONNECTED (unreachable, IP already failed over)",
                    "crit",
                ),
                required=True,
            ),
            "banned_state": DictElement(
                parameter_form=_state_choice(
                    "State for BANNED (booted for repeated recovery failures)",
                    "crit",
                ),
                required=True,
            ),
            "recovery_grace_period": DictElement(
                parameter_form=Integer(
                    title=Title("Grace period before RECOVERY mode is 'stuck'"),
                    help_text=Help(
                        "A brief RECOVERY blip during normal failover is "
                        "expected and stays WARN. If recovery mode hasn't "
                        "cleared within this many seconds, severity escalates "
                        "to the state configured below."
                    ),
                    unit_symbol="s",
                    prefill=DefaultValue(30),
                ),
                required=True,
            ),
            "recovery_stuck_state": DictElement(
                parameter_form=_state_choice(
                    "State once the RECOVERY grace period is exceeded",
                    "crit",
                ),
                required=True,
            ),
        },
    )


rule_spec_ctdb_cluster_health = CheckParameters(
    name="ctdb_cluster_health",
    title=Title("CTDB Cluster Health"),
    topic=Topic.APPLICATIONS,
    parameter_form=_parameter_form_ctdb_cluster_health,
    condition=HostCondition(),
)