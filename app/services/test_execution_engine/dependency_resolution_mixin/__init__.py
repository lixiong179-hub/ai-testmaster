from app.services.test_execution_engine.dependency_resolution_mixin._graph import _DependencyGraphMixin
from app.services.test_execution_engine.dependency_resolution_mixin._snapshot import _SnapshotMixin
from app.services.test_execution_engine.dependency_resolution_mixin._navigation import _NavigationMixin
from app.services.test_execution_engine.dependency_resolution_mixin._orchestration import _OrchestrationMixin


class DependencyResolutionMixin(
    _DependencyGraphMixin,
    _SnapshotMixin,
    _NavigationMixin,
    _OrchestrationMixin,
):
    pass


__all__ = ["DependencyResolutionMixin"]
