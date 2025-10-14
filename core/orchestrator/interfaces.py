"""
Orchestrator interfaces for the REDO system.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

from core.types import QueryContext, OrchestrationResult, OrchestrationConfig


class Orchestrator(ABC):
    """Abstract base class for orchestrators."""
    
    @abstractmethod
    def run(self, query_ctx: QueryContext) -> OrchestrationResult:
        """
        Run orchestration for a given query context.
        
        Args:
            query_ctx: The query context to orchestrate
            
        Returns:
            OrchestrationResult containing stages, final plan, timings, and warnings
        """
        pass
    
    @abstractmethod
    def configure(self, config: OrchestrationConfig) -> None:
        """
        Configure the orchestrator with the given configuration.
        
        Args:
            config: The orchestration configuration
        """
        pass


@runtime_checkable
class OrchestratorProtocol(Protocol):
    """Protocol for orchestrator implementations."""
    
    def run(self, query_ctx: QueryContext) -> OrchestrationResult:
        """Run orchestration for a given query context."""
        ...
    
    def configure(self, config: OrchestrationConfig) -> None:
        """Configure the orchestrator with the given configuration."""
        ...


class StageProcessor(ABC):
    """Abstract base class for stage processors."""
    
    @abstractmethod
    def process(self, input_data: dict, context: QueryContext) -> dict:
        """
        Process a stage with the given input data and context.
        
        Args:
            input_data: Input data for the stage
            context: The query context
            
        Returns:
            Output data from the stage
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Get the name of this stage processor."""
        pass


class ContradictionDetector(ABC):
    """Abstract base class for contradiction detectors."""
    
    @abstractmethod
    def detect(self, context_data: dict) -> list[dict]:
        """
        Detect contradictions in the given context data.
        
        Args:
            context_data: The context data to analyze
            
        Returns:
            List of detected contradictions
        """
        pass


class PlanGenerator(ABC):
    """Abstract base class for plan generators."""
    
    @abstractmethod
    def generate(self, stages: list, context: QueryContext) -> dict:
        """
        Generate a final plan from the orchestration stages.
        
        Args:
            stages: List of completed stages
            context: The query context
            
        Returns:
            The final plan
        """
        pass