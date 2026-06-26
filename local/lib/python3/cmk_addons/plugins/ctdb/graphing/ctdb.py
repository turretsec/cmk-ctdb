from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Graph
from cmk.graphing.v1.metrics import Color, Metric, TimeNotation, Unit

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

metric_ctdb_recovery_elapsed = Metric(
    name="ctdb_recovery_elapsed",
    title=Title("CTDB recovery mode elapsed time"),
    unit=Unit(TimeNotation()),
    color=Color.ORANGE,
)

# ---------------------------------------------------------------------------
# Graphs
# ---------------------------------------------------------------------------

graph_ctdb_recovery_elapsed = Graph(
    name="ctdb_recovery_elapsed",
    title=Title("CTDB Recovery Mode Duration"),
    simple_lines=["ctdb_recovery_elapsed"],
)