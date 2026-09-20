"""DecisionRouter: the common interface every router must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from jevroute.models.decision import DecisionResult
from jevroute.models.state import ApplicationState


@runtime_checkable
class DecisionRouter(Protocol):
    """Protocol that every router implementation must satisfy.

    The benchmark runner treats all routers identically through this interface.
    No router receives special treatment from the runner or policy engine.
    (JevRoute_MVP_Technical_Architecture.md §6.3)

    Implementations:
        RulesRouter       — Phase 2
        LLMSingleRouter   — Phase 2
        LLMParallelRouter — Phase 2
        JevRouter         — Phase 3
        MockJevRouter     — Phase 1 (CI/dev only)
    """

    async def decide(self, state: ApplicationState) -> DecisionResult:
        """Produce a normalized DecisionResult for the given ApplicationState.

        Contract:
        - One input state produces exactly one DecisionResult.
        - Policy logic must NOT be applied inside this method.
        - All latency and cost metadata must be recorded in the result.
        - Errors must propagate, never be silently swallowed.
        """
        ...
