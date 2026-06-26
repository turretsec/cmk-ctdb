from cmk.rulesets.v1 import Help, Title
from cmk.rulesets.v1.form_specs import DefaultValue, DictElement, Dictionary, Integer
from cmk.rulesets.v1.rule_specs import AgentConfig, Topic


def _form_ctdb_bakery() -> Dictionary:
    return Dictionary(
        title=Title("CTDB Cluster Monitoring"),
        help_text=Help(
            "Deploys the ctdb_status agent plugin to Linux hosts that are "
            "nodes in a CTDB cluster. The plugin runs `ctdb status` and "
            "`ctdb ip all` locally and reports cluster health and public "
            "IP allocation. "
            "Deploy this identically to every node in the cluster. Both "
            "ctdb commands return a cluster-wide view regardless of which "
            "node you ask, so running it on every node gives redundant "
            "visibility rather than duplicated work. If one node's agent "
            "goes dark, the others still carry the full cluster picture. "
            "Severity thresholds are configured separately under "
            "Setup -> Service monitoring rules -> Applications -> "
            "CTDB Cluster Health / CTDB Public IP Allocation. "
            "All settings here are optional."
        ),
        elements={
            "timeout": DictElement(
                required=False,
                parameter_form=Integer(
                    title=Title("ctdb command timeout (seconds)"),
                    help_text=Help(
                        "How long to wait for `ctdb status` / `ctdb ip all` "
                        "to respond before giving up and reporting an error "
                        "section. Default: 15."
                    ),
                    prefill=DefaultValue(15),
                ),
            ),
        },
    )


rule_spec_ctdb_bakery = AgentConfig(
    name="ctdb",
    title=Title("CTDB Cluster Monitoring"),
    topic=Topic.APPLICATIONS,
    parameter_form=_form_ctdb_bakery,
)