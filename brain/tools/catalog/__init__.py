"""The household tool catalog. Adding a capability = add a Tool in one of
these modules; the orchestrator, gating and tracing pick it up automatically."""

from brain.tools.catalog import calendar, household_admin, lists, meals
from brain.tools.registry import ToolRegistry


def build_registry() -> ToolRegistry:
    registry = ToolRegistry()
    for module in (calendar, household_admin, meals, lists):
        module.register(registry)
    return registry
