# core/aura/bridge.py — Aura bridge logic for project creation from hypotheses

import time
import hashlib
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum

from core.factare.summary import CompareSummary, EvidenceItem
from core.hypotheses.propose import HypothesisProposal, HypothesisStatus

class ProjectStatus(Enum):
    """Status of an Aura project."""
    PROPOSED = "proposed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

class TaskStatus(Enum):
    """Status of an Aura task."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"

class TaskPriority(Enum):
    """Priority of an Aura task."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class AuraProject:
    """An Aura project created from a hypothesis."""
    id: str
    title: str
    description: str
    hypothesis_id: str
    status: ProjectStatus
    created_at: datetime
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuraProject':
        """Create from dictionary."""
        created_at = datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now()
        status = ProjectStatus(data.get('status', 'proposed'))
        
        return cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            hypothesis_id=data['hypothesis_id'],
            status=status,
            created_at=created_at,
            created_by=data.get('created_by'),
            metadata=data.get('metadata')
        )

@dataclass
class AuraTask:
    """An Aura task generated from project evidence."""
    id: str
    project_id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    evidence_id: Optional[str] = None
    evidence_source: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        data['status'] = self.status.value
        data['priority'] = self.priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuraTask':
        """Create from dictionary."""
        created_at = datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now()
        status = TaskStatus(data.get('status', 'todo'))
        priority = TaskPriority(data.get('priority', 'medium'))
        
        return cls(
            id=data['id'],
            project_id=data['project_id'],
            title=data['title'],
            description=data['description'],
            status=status,
            priority=priority,
            evidence_id=data.get('evidence_id'),
            evidence_source=data.get('evidence_source'),
            created_at=created_at,
            created_by=data.get('created_by'),
            metadata=data.get('metadata')
        )

@dataclass
class ProjectCreationResult:
    """Result of project creation from hypothesis."""
    project: AuraProject
    tasks: List[AuraTask]
    hypothesis_used: HypothesisProposal
    created_at: datetime
    metadata: Dict[str, Any]

class TaskGenerator:
    """Generates starter tasks from compare_summary evidence."""
    
    def __init__(self):
        self.task_templates = {
            'data_collection': [
                "Collect dataset: {source}",
                "Gather {source} data for analysis",
                "Compile {source} information"
            ],
            'replication': [
                "Replicate {source} findings",
                "Verify {source} results",
                "Test {source} methodology"
            ],
            'analysis': [
                "Analyze {source} evidence",
                "Evaluate {source} claims",
                "Investigate {source} implications"
            ],
            'validation': [
                "Validate {source} conclusions",
                "Cross-check {source} data",
                "Confirm {source} accuracy"
            ]
        }
    
    def generate_tasks_from_evidence(
        self,
        evidence_items: List[EvidenceItem],
        project_id: str,
        max_tasks: int = 3,
        created_by: Optional[str] = None
    ) -> List[AuraTask]:
        """
        Generate starter tasks from evidence items.
        
        Args:
            evidence_items: List of evidence items from compare_summary
            project_id: ID of the project these tasks belong to
            max_tasks: Maximum number of tasks to generate
            created_by: User who created the tasks
            
        Returns:
            List of generated AuraTask objects
        """
        if not evidence_items:
            return []
        
        tasks = []
        task_id_counter = 1
        
        # Sort evidence by score (highest first)
        sorted_evidence = sorted(evidence_items, key=lambda x: x.score, reverse=True)
        
        # Take top evidence items for task generation
        top_evidence = sorted_evidence[:max_tasks]
        
        for i, evidence in enumerate(top_evidence):
            # Determine task type based on evidence characteristics
            task_type = self._determine_task_type(evidence)
            template = self._select_template(task_type)
            
            # Generate task title and description
            title = template.format(source=evidence.source)
            description = self._generate_task_description(evidence, task_type)
            
            # Determine priority based on evidence score
            priority = self._determine_priority(evidence.score)
            
            # Create task
            task = AuraTask(
                id=f"task_{project_id}_{task_id_counter:03d}",
                project_id=project_id,
                title=title,
                description=description,
                status=TaskStatus.TODO,
                priority=priority,
                evidence_id=evidence.id,
                evidence_source=evidence.source,
                created_at=datetime.now(),
                created_by=created_by,
                metadata={
                    'task_type': task_type,
                    'evidence_score': evidence.score,
                    'evidence_snippet': evidence.snippet[:200] + "..." if len(evidence.snippet) > 200 else evidence.snippet,
                    'generated_from': 'compare_summary_evidence'
                }
            )
            
            tasks.append(task)
            task_id_counter += 1
        
        return tasks
    
    def _determine_task_type(self, evidence: EvidenceItem) -> str:
        """Determine task type based on evidence characteristics."""
        snippet_lower = evidence.snippet.lower()
        source_lower = evidence.source.lower()
        
        # Check for data collection indicators
        if any(keyword in snippet_lower for keyword in ['data', 'dataset', 'collect', 'gather', 'compile']):
            return 'data_collection'
        
        # Check for replication indicators
        if any(keyword in snippet_lower for keyword in ['replicate', 'verify', 'test', 'repeat', 'confirm']):
            return 'replication'
        
        # Check for analysis indicators
        if any(keyword in snippet_lower for keyword in ['analyze', 'evaluate', 'investigate', 'study', 'examine']):
            return 'analysis'
        
        # Check for validation indicators
        if any(keyword in snippet_lower for keyword in ['validate', 'cross-check', 'confirm', 'verify', 'check']):
            return 'validation'
        
        # Default based on source type
        if 'research' in source_lower or 'study' in source_lower:
            return 'analysis'
        elif 'data' in source_lower or 'database' in source_lower:
            return 'data_collection'
        else:
            return 'validation'
    
    def _select_template(self, task_type: str) -> str:
        """Select a template for the given task type."""
        templates = self.task_templates.get(task_type, self.task_templates['validation'])
        import random
        return random.choice(templates)
    
    def _generate_task_description(self, evidence: EvidenceItem, task_type: str) -> str:
        """Generate detailed task description from evidence."""
        base_description = f"Task generated from evidence: {evidence.snippet[:100]}..."
        
        if task_type == 'data_collection':
            return f"{base_description}\n\nFocus on gathering comprehensive data from {evidence.source} to support the hypothesis."
        elif task_type == 'replication':
            return f"{base_description}\n\nAim to replicate the findings or methodology described in {evidence.source}."
        elif task_type == 'analysis':
            return f"{base_description}\n\nConduct thorough analysis of the evidence from {evidence.source}."
        elif task_type == 'validation':
            return f"{base_description}\n\nValidate the claims and conclusions presented in {evidence.source}."
        else:
            return f"{base_description}\n\nInvestigate the evidence from {evidence.source}."
    
    def _determine_priority(self, evidence_score: float) -> TaskPriority:
        """Determine task priority based on evidence score."""
        if evidence_score >= 0.8:
            return TaskPriority.HIGH
        elif evidence_score >= 0.6:
            return TaskPriority.MEDIUM
        else:
            return TaskPriority.LOW

class AuraBridge:
    """Main bridge class for creating Aura projects from hypotheses."""
    
    def __init__(self):
        self.task_generator = TaskGenerator()
        self._projects_db = {}  # Simulated database
        self._tasks_db = {}     # Simulated database
        self._next_project_id = 1
        self._next_task_id = 1
    
    def create_project_from_hypothesis(
        self,
        hypothesis_id: str,
        hypothesis: HypothesisProposal,
        title: Optional[str] = None,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> ProjectCreationResult:
        """
        Create an Aura project from a hypothesis.
        
        Args:
            hypothesis_id: ID of the hypothesis
            hypothesis: Hypothesis proposal object
            title: Optional custom project title
            description: Optional custom project description
            created_by: User creating the project
            
        Returns:
            ProjectCreationResult with project, tasks, and metadata
            
        Raises:
            ValueError: If hypothesis status is invalid
        """
        # Validate hypothesis status
        if hypothesis.status not in [HypothesisStatus.PENDING, HypothesisStatus.APPROVED]:
            raise ValueError(f"Hypothesis status '{hypothesis.status.value}' is not valid for project creation. Must be 'pending' or 'approved'.")
        
        # Generate project ID
        project_id = f"proj_{self._next_project_id:06d}"
        self._next_project_id += 1
        
        # Use provided title/description or generate from hypothesis
        project_title = title or f"Project: {hypothesis.title}"
        project_description = description or f"Project based on hypothesis: {hypothesis.description}"
        
        # Create project
        project = AuraProject(
            id=project_id,
            title=project_title,
            description=project_description,
            hypothesis_id=hypothesis_id,
            status=ProjectStatus.PROPOSED,
            created_at=datetime.now(),
            created_by=created_by,
            metadata={
                'source_hypothesis': hypothesis_id,
                'hypothesis_title': hypothesis.title,
                'hypothesis_pareto_score': hypothesis.pareto_score,
                'created_from_bridge': True,
                'creation_timestamp': datetime.now().isoformat()
            }
        )
        
        # Generate starter tasks from compare_summary evidence
        tasks = []
        if hypothesis.compare_summary and hypothesis.compare_summary.evidence:
            tasks = self.task_generator.generate_tasks_from_evidence(
                evidence_items=hypothesis.compare_summary.evidence,
                project_id=project_id,
                max_tasks=3,
                created_by=created_by
            )
        
        # Store project and tasks
        self._projects_db[project_id] = project
        for task in tasks:
            self._tasks_db[task.id] = task
        
        # Create result
        result = ProjectCreationResult(
            project=project,
            tasks=tasks,
            hypothesis_used=hypothesis,
            created_at=datetime.now(),
            metadata={
                'tasks_generated': len(tasks),
                'evidence_items_used': len(hypothesis.compare_summary.evidence) if hypothesis.compare_summary else 0,
                'project_created': True,
                'bridge_version': '1.0.0'
            }
        )
        
        return result
    
    def get_project(self, project_id: str) -> Optional[AuraProject]:
        """Get project by ID."""
        return self._projects_db.get(project_id)
    
    def get_project_tasks(self, project_id: str) -> List[AuraTask]:
        """Get all tasks for a project."""
        return [task for task in self._tasks_db.values() if task.project_id == project_id]
    
    def list_projects(
        self,
        status: Optional[ProjectStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuraProject]:
        """List projects with optional filtering."""
        projects = list(self._projects_db.values())
        
        if status:
            projects = [p for p in projects if p.status == status]
        
        # Sort by created_at descending
        projects.sort(key=lambda p: p.created_at, reverse=True)
        
        return projects[offset:offset + limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about projects and tasks."""
        total_projects = len(self._projects_db)
        total_tasks = len(self._tasks_db)
        
        # Count by status
        project_status_counts = {}
        for project in self._projects_db.values():
            status = project.status.value
            project_status_counts[status] = project_status_counts.get(status, 0) + 1
        
        task_status_counts = {}
        for task in self._tasks_db.values():
            status = task.status.value
            task_status_counts[status] = task_status_counts.get(status, 0) + 1
        
        # Count projects with tasks
        projects_with_tasks = sum(1 for project in self._projects_db.values() 
                                if any(task.project_id == project.id for task in self._tasks_db.values()))
        
        return {
            'total_projects': total_projects,
            'total_tasks': total_tasks,
            'projects_by_status': project_status_counts,
            'tasks_by_status': task_status_counts,
            'projects_with_tasks': projects_with_tasks,
            'average_tasks_per_project': total_tasks / max(1, total_projects),
            'bridge_version': '1.0.0'
        }

# Global bridge instance
_aura_bridge = None

def get_aura_bridge() -> AuraBridge:
    """Get the global Aura bridge instance."""
    global _aura_bridge
    if _aura_bridge is None:
        _aura_bridge = AuraBridge()
    return _aura_bridge

# Convenience function for direct project creation
def create_project_from_hypothesis(
    hypothesis_id: str,
    hypothesis: HypothesisProposal,
    title: Optional[str] = None,
    description: Optional[str] = None,
    created_by: Optional[str] = None
) -> ProjectCreationResult:
    """
    Convenience function for creating a project from a hypothesis.
    
    Args:
        hypothesis_id: ID of the hypothesis
        hypothesis: Hypothesis proposal object
        title: Optional custom project title
        description: Optional custom project description
        created_by: User creating the project
        
    Returns:
        ProjectCreationResult with project, tasks, and metadata
    """
    bridge = get_aura_bridge()
    return bridge.create_project_from_hypothesis(
        hypothesis_id=hypothesis_id,
        hypothesis=hypothesis,
        title=title,
        description=description,
        created_by=created_by
    )