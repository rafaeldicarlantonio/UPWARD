# tests/test_aura_bridge.py — Comprehensive tests for Aura bridge functionality

import unittest
import sys
import os
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add workspace to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the config loading before importing
with patch.dict(os.environ, {
    'OPENAI_API_KEY': 'test-key',
    'SUPABASE_URL': 'https://test.supabase.co',
    'PINECONE_API_KEY': 'test-pinecone-key',
    'PINECONE_INDEX': 'test-index',
    'PINECONE_EXPLICATE_INDEX': 'test-explicate',
    'PINECONE_IMPLICATE_INDEX': 'test-implicate',
}):
    from core.aura.bridge import (
        AuraProject,
        AuraTask,
        ProjectStatus,
        TaskStatus,
        TaskPriority,
        TaskGenerator,
        AuraBridge,
        ProjectCreationResult,
        create_project_from_hypothesis
    )
    from core.hypotheses.propose import HypothesisProposal, HypothesisStatus
    from core.factare.summary import CompareSummary, EvidenceItem, Decision

class TestAuraProject(unittest.TestCase):
    """Test AuraProject dataclass."""
    
    def test_aura_project_creation(self):
        """Test creating an Aura project."""
        now = datetime.now()
        
        project = AuraProject(
            id="proj_001",
            title="Test Project",
            description="Test project description",
            hypothesis_id="hyp_001",
            status=ProjectStatus.PROPOSED,
            created_at=now,
            created_by="test_user",
            metadata={"test": "value"}
        )
        
        self.assertEqual(project.id, "proj_001")
        self.assertEqual(project.title, "Test Project")
        self.assertEqual(project.description, "Test project description")
        self.assertEqual(project.hypothesis_id, "hyp_001")
        self.assertEqual(project.status, ProjectStatus.PROPOSED)
        self.assertEqual(project.created_at, now)
        self.assertEqual(project.created_by, "test_user")
        self.assertEqual(project.metadata["test"], "value")
    
    def test_aura_project_to_dict(self):
        """Test converting project to dictionary."""
        now = datetime.now()
        
        project = AuraProject(
            id="proj_001",
            title="Test Project",
            description="Test project description",
            hypothesis_id="hyp_001",
            status=ProjectStatus.PROPOSED,
            created_at=now,
            created_by="test_user",
            metadata={"test": "value"}
        )
        
        data = project.to_dict()
        
        self.assertEqual(data['id'], "proj_001")
        self.assertEqual(data['title'], "Test Project")
        self.assertEqual(data['description'], "Test project description")
        self.assertEqual(data['hypothesis_id'], "hyp_001")
        self.assertEqual(data['status'], "proposed")
        self.assertEqual(data['created_at'], now.isoformat())
        self.assertEqual(data['created_by'], "test_user")
        self.assertEqual(data['metadata']['test'], "value")
    
    def test_aura_project_from_dict(self):
        """Test creating project from dictionary."""
        now = datetime.now()
        
        data = {
            'id': 'proj_001',
            'title': 'Test Project',
            'description': 'Test project description',
            'hypothesis_id': 'hyp_001',
            'status': 'proposed',
            'created_at': now.isoformat(),
            'created_by': 'test_user',
            'metadata': {'test': 'value'}
        }
        
        project = AuraProject.from_dict(data)
        
        self.assertEqual(project.id, "proj_001")
        self.assertEqual(project.title, "Test Project")
        self.assertEqual(project.description, "Test project description")
        self.assertEqual(project.hypothesis_id, "hyp_001")
        self.assertEqual(project.status, ProjectStatus.PROPOSED)
        self.assertEqual(project.created_at, now)
        self.assertEqual(project.created_by, "test_user")
        self.assertEqual(project.metadata['test'], "value")

class TestAuraTask(unittest.TestCase):
    """Test AuraTask dataclass."""
    
    def test_aura_task_creation(self):
        """Test creating an Aura task."""
        now = datetime.now()
        
        task = AuraTask(
            id="task_001",
            project_id="proj_001",
            title="Test Task",
            description="Test task description",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            evidence_id="ev_001",
            evidence_source="Test Source",
            created_at=now,
            created_by="test_user",
            metadata={"test": "value"}
        )
        
        self.assertEqual(task.id, "task_001")
        self.assertEqual(task.project_id, "proj_001")
        self.assertEqual(task.title, "Test Task")
        self.assertEqual(task.description, "Test task description")
        self.assertEqual(task.status, TaskStatus.TODO)
        self.assertEqual(task.priority, TaskPriority.HIGH)
        self.assertEqual(task.evidence_id, "ev_001")
        self.assertEqual(task.evidence_source, "Test Source")
        self.assertEqual(task.created_at, now)
        self.assertEqual(task.created_by, "test_user")
        self.assertEqual(task.metadata["test"], "value")
    
    def test_aura_task_to_dict(self):
        """Test converting task to dictionary."""
        now = datetime.now()
        
        task = AuraTask(
            id="task_001",
            project_id="proj_001",
            title="Test Task",
            description="Test task description",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            evidence_id="ev_001",
            evidence_source="Test Source",
            created_at=now,
            created_by="test_user",
            metadata={"test": "value"}
        )
        
        data = task.to_dict()
        
        self.assertEqual(data['id'], "task_001")
        self.assertEqual(data['project_id'], "proj_001")
        self.assertEqual(data['title'], "Test Task")
        self.assertEqual(data['description'], "Test task description")
        self.assertEqual(data['status'], "todo")
        self.assertEqual(data['priority'], "high")
        self.assertEqual(data['evidence_id'], "ev_001")
        self.assertEqual(data['evidence_source'], "Test Source")
        self.assertEqual(data['created_at'], now.isoformat())
        self.assertEqual(data['created_by'], "test_user")
        self.assertEqual(data['metadata']['test'], "value")

class TestTaskGenerator(unittest.TestCase):
    """Test TaskGenerator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = TaskGenerator()
        self.now = datetime.now()
        
        # Sample evidence items
        self.sample_evidence = [
            EvidenceItem(
                id="ev_001",
                snippet="AI implementation increases efficiency by 40%",
                source="Internal Research",
                score=0.9,
                is_external=False
            ),
            EvidenceItem(
                id="ev_002",
                snippet="AI poses security risks in enterprise environments",
                source="Security Analysis",
                score=0.7,
                is_external=False
            ),
            EvidenceItem(
                id="ev_003",
                snippet="AI adoption shows mixed results across industries",
                source="Industry Report",
                score=0.5,
                is_external=True
            )
        ]
    
    def test_generate_tasks_from_evidence(self):
        """Test generating tasks from evidence items."""
        tasks = self.generator.generate_tasks_from_evidence(
            evidence_items=self.sample_evidence,
            project_id="proj_001",
            max_tasks=3,
            created_by="test_user"
        )
        
        self.assertEqual(len(tasks), 3)
        
        for i, task in enumerate(tasks):
            self.assertIsInstance(task, AuraTask)
            self.assertEqual(task.project_id, "proj_001")
            self.assertEqual(task.status, TaskStatus.TODO)
            self.assertIn(task.priority, [TaskPriority.LOW, TaskPriority.MEDIUM, TaskPriority.HIGH])
            self.assertIsNotNone(task.evidence_id)
            self.assertIsNotNone(task.evidence_source)
            self.assertEqual(task.created_by, "test_user")
            self.assertIn('task_type', task.metadata)
            self.assertIn('evidence_score', task.metadata)
    
    def test_generate_tasks_empty_evidence(self):
        """Test generating tasks with empty evidence."""
        tasks = self.generator.generate_tasks_from_evidence(
            evidence_items=[],
            project_id="proj_001",
            max_tasks=3,
            created_by="test_user"
        )
        
        self.assertEqual(len(tasks), 0)
    
    def test_determine_task_type(self):
        """Test task type determination."""
        # Data collection evidence
        data_evidence = EvidenceItem(
            id="ev_001",
            snippet="Collect dataset for analysis",
            source="Data Source",
            score=0.8,
            is_external=False
        )
        task_type = self.generator._determine_task_type(data_evidence)
        self.assertEqual(task_type, 'data_collection')
        
        # Replication evidence
        replication_evidence = EvidenceItem(
            id="ev_002",
            snippet="Replicate the findings from the study",
            source="Research Paper",
            score=0.7,
            is_external=False
        )
        task_type = self.generator._determine_task_type(replication_evidence)
        self.assertEqual(task_type, 'replication')
        
        # Analysis evidence
        analysis_evidence = EvidenceItem(
            id="ev_003",
            snippet="Analyze the results and implications",
            source="Analysis Report",
            score=0.6,
            is_external=False
        )
        task_type = self.generator._determine_task_type(analysis_evidence)
        self.assertEqual(task_type, 'analysis')
        
        # Validation evidence
        validation_evidence = EvidenceItem(
            id="ev_004",
            snippet="Validate the conclusions",
            source="Validation Study",
            score=0.5,
            is_external=False
        )
        task_type = self.generator._determine_task_type(validation_evidence)
        self.assertEqual(task_type, 'validation')
    
    def test_determine_priority(self):
        """Test priority determination based on evidence score."""
        # High priority (score >= 0.8)
        priority = self.generator._determine_priority(0.9)
        self.assertEqual(priority, TaskPriority.HIGH)
        
        # Medium priority (0.6 <= score < 0.8)
        priority = self.generator._determine_priority(0.7)
        self.assertEqual(priority, TaskPriority.MEDIUM)
        
        # Low priority (score < 0.6)
        priority = self.generator._determine_priority(0.5)
        self.assertEqual(priority, TaskPriority.LOW)
    
    def test_generate_task_description(self):
        """Test task description generation."""
        evidence = EvidenceItem(
            id="ev_001",
            snippet="AI implementation increases efficiency by 40%",
            source="Internal Research",
            score=0.9,
            is_external=False
        )
        
        description = self.generator._generate_task_description(evidence, 'data_collection')
        
        self.assertIn("AI implementation increases efficiency by 40%", description)
        self.assertIn("Internal Research", description)
        self.assertIn("data collection", description.lower())

class TestAuraBridge(unittest.TestCase):
    """Test AuraBridge functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bridge = AuraBridge()
        self.now = datetime.now()
        
        # Sample hypothesis
        self.sample_hypothesis = HypothesisProposal(
            title="AI Efficiency Hypothesis",
            description="AI implementation improves efficiency",
            source_message_id="msg_001",
            pareto_score=0.8,
            created_at=self.now,
            created_by="researcher",
            status=HypothesisStatus.PENDING,
            metadata={}
        )
        
        # Sample hypothesis with compare_summary
        self.sample_hypothesis_with_evidence = HypothesisProposal(
            title="AI Security Hypothesis",
            description="AI poses security risks",
            source_message_id="msg_002",
            pareto_score=0.7,
            created_at=self.now,
            created_by="researcher",
            status=HypothesisStatus.APPROVED,
            metadata={},
            compare_summary=CompareSummary(
                query="Should we adopt AI?",
                stance_a="AI is beneficial",
                stance_b="AI is risky",
                evidence=[
                    EvidenceItem(
                        id="ev_001",
                        snippet="AI increases efficiency",
                        source="Research",
                        score=0.9,
                        is_external=False
                    ),
                    EvidenceItem(
                        id="ev_002",
                        snippet="AI poses security risks",
                        source="Security Analysis",
                        score=0.7,
                        is_external=False
                    )
                ],
                decision=Decision(
                    verdict="inconclusive",
                    confidence=0.6,
                    rationale="Mixed evidence"
                ),
                created_at=self.now,
                metadata={}
            )
        )
    
    def test_create_project_from_hypothesis(self):
        """Test creating project from hypothesis."""
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_001",
            hypothesis=self.sample_hypothesis,
            created_by="test_user"
        )
        
        self.assertIsInstance(result, ProjectCreationResult)
        self.assertIsInstance(result.project, AuraProject)
        self.assertEqual(result.project.hypothesis_id, "hyp_001")
        self.assertEqual(result.project.status, ProjectStatus.PROPOSED)
        self.assertEqual(result.project.created_by, "test_user")
        self.assertEqual(len(result.tasks), 0)  # No evidence, so no tasks
    
    def test_create_project_from_hypothesis_with_evidence(self):
        """Test creating project from hypothesis with evidence."""
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_002",
            hypothesis=self.sample_hypothesis_with_evidence,
            created_by="test_user"
        )
        
        self.assertIsInstance(result, ProjectCreationResult)
        self.assertIsInstance(result.project, AuraProject)
        self.assertEqual(result.project.hypothesis_id, "hyp_002")
        self.assertEqual(result.project.status, ProjectStatus.PROPOSED)
        self.assertEqual(result.project.created_by, "test_user")
        self.assertEqual(len(result.tasks), 2)  # Two evidence items
        
        for task in result.tasks:
            self.assertIsInstance(task, AuraTask)
            self.assertEqual(task.project_id, result.project.id)
            self.assertEqual(task.status, TaskStatus.TODO)
            self.assertIsNotNone(task.evidence_id)
            self.assertIsNotNone(task.evidence_source)
    
    def test_create_project_with_custom_title_description(self):
        """Test creating project with custom title and description."""
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_001",
            hypothesis=self.sample_hypothesis,
            title="Custom Project Title",
            description="Custom project description",
            created_by="test_user"
        )
        
        self.assertEqual(result.project.title, "Custom Project Title")
        self.assertEqual(result.project.description, "Custom project description")
    
    def test_create_project_invalid_status(self):
        """Test creating project with invalid hypothesis status."""
        invalid_hypothesis = HypothesisProposal(
            title="Invalid Hypothesis",
            description="This has invalid status",
            source_message_id="msg_003",
            pareto_score=0.5,
            created_at=self.now,
            created_by="researcher",
            status=HypothesisStatus.REJECTED,  # Invalid status
            metadata={}
        )
        
        with self.assertRaises(ValueError) as context:
            self.bridge.create_project_from_hypothesis(
                hypothesis_id="hyp_003",
                hypothesis=invalid_hypothesis,
                created_by="test_user"
            )
        
        self.assertIn("not valid for project creation", str(context.exception))
    
    def test_get_project(self):
        """Test retrieving project by ID."""
        # First create a project
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_001",
            hypothesis=self.sample_hypothesis,
            created_by="test_user"
        )
        
        project_id = result.project.id
        
        # Retrieve the project
        project = self.bridge.get_project(project_id)
        self.assertIsNotNone(project)
        self.assertEqual(project.id, project_id)
        self.assertEqual(project.hypothesis_id, "hyp_001")
    
    def test_get_project_not_found(self):
        """Test retrieving non-existent project."""
        project = self.bridge.get_project("nonexistent")
        self.assertIsNone(project)
    
    def test_get_project_tasks(self):
        """Test retrieving tasks for a project."""
        # Create project with evidence
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_002",
            hypothesis=self.sample_hypothesis_with_evidence,
            created_by="test_user"
        )
        
        project_id = result.project.id
        tasks = self.bridge.get_project_tasks(project_id)
        
        self.assertEqual(len(tasks), 2)
        for task in tasks:
            self.assertEqual(task.project_id, project_id)
    
    def test_list_projects(self):
        """Test listing projects."""
        # Create multiple projects
        result1 = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_001",
            hypothesis=self.sample_hypothesis,
            created_by="test_user"
        )
        
        result2 = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_002",
            hypothesis=self.sample_hypothesis_with_evidence,
            created_by="test_user"
        )
        
        # List all projects
        projects = self.bridge.list_projects()
        self.assertEqual(len(projects), 2)
        
        # List with status filter
        proposed_projects = self.bridge.list_projects(status=ProjectStatus.PROPOSED)
        self.assertEqual(len(proposed_projects), 2)
        
        # List with limit
        limited_projects = self.bridge.list_projects(limit=1)
        self.assertEqual(len(limited_projects), 1)
    
    def test_get_stats(self):
        """Test getting statistics."""
        # Create some projects and tasks
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_001",
            hypothesis=self.sample_hypothesis_with_evidence,
            created_by="test_user"
        )
        
        stats = self.bridge.get_stats()
        
        self.assertEqual(stats['total_projects'], 1)
        self.assertEqual(stats['total_tasks'], 2)
        self.assertIn('projects_by_status', stats)
        self.assertIn('tasks_by_status', stats)
        self.assertEqual(stats['projects_with_tasks'], 1)
        self.assertEqual(stats['average_tasks_per_project'], 2.0)

class TestConvenienceFunction(unittest.TestCase):
    """Test convenience function for project creation."""
    
    def test_create_project_from_hypothesis_convenience(self):
        """Test the convenience function for project creation."""
        hypothesis = HypothesisProposal(
            title="Test Hypothesis",
            description="Test description",
            source_message_id="msg_001",
            pareto_score=0.8,
            created_at=datetime.now(),
            created_by="researcher",
            status=HypothesisStatus.PENDING,
            metadata={}
        )
        
        result = create_project_from_hypothesis(
            hypothesis_id="hyp_001",
            hypothesis=hypothesis,
            created_by="test_user"
        )
        
        self.assertIsInstance(result, ProjectCreationResult)
        self.assertIsInstance(result.project, AuraProject)
        self.assertEqual(result.project.hypothesis_id, "hyp_001")

class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bridge = AuraBridge()
        self.now = datetime.now()
    
    def test_full_workflow_with_evidence(self):
        """Test full workflow with evidence-based task generation."""
        # Create hypothesis with evidence
        hypothesis = HypothesisProposal(
            title="AI Implementation Hypothesis",
            description="AI implementation improves productivity",
            source_message_id="msg_001",
            pareto_score=0.8,
            created_at=self.now,
            created_by="researcher",
            status=HypothesisStatus.APPROVED,
            metadata={},
            compare_summary=CompareSummary(
                query="Should we implement AI?",
                stance_a="AI is beneficial",
                stance_b="AI is risky",
                evidence=[
                    EvidenceItem(
                        id="ev_001",
                        snippet="AI increases efficiency by 40%",
                        source="Internal Research",
                        score=0.9,
                        is_external=False
                    ),
                    EvidenceItem(
                        id="ev_002",
                        snippet="AI poses security risks",
                        source="Security Analysis",
                        score=0.7,
                        is_external=False
                    ),
                    EvidenceItem(
                        id="ev_003",
                        snippet="AI adoption shows mixed results",
                        source="Industry Report",
                        score=0.5,
                        is_external=True
                    )
                ],
                decision=Decision(
                    verdict="inconclusive",
                    confidence=0.6,
                    rationale="Mixed evidence"
                ),
                created_at=self.now,
                metadata={}
            )
        )
        
        # Create project
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_001",
            hypothesis=hypothesis,
            title="AI Implementation Project",
            description="Project to implement AI based on hypothesis",
            created_by="project_manager"
        )
        
        # Verify project
        self.assertEqual(result.project.title, "AI Implementation Project")
        self.assertEqual(result.project.description, "Project to implement AI based on hypothesis")
        self.assertEqual(result.project.hypothesis_id, "hyp_001")
        self.assertEqual(result.project.status, ProjectStatus.PROPOSED)
        self.assertEqual(result.project.created_by, "project_manager")
        
        # Verify tasks
        self.assertEqual(len(result.tasks), 3)
        
        # Check task details
        for i, task in enumerate(result.tasks):
            self.assertEqual(task.project_id, result.project.id)
            self.assertEqual(task.status, TaskStatus.TODO)
            self.assertIsNotNone(task.evidence_id)
            self.assertIsNotNone(task.evidence_source)
            self.assertEqual(task.created_by, "project_manager")
            self.assertIn('task_type', task.metadata)
            self.assertIn('evidence_score', task.metadata)
        
        # Verify task priorities (should be based on evidence scores)
        priorities = [task.priority for task in result.tasks]
        self.assertIn(TaskPriority.HIGH, priorities)  # Score 0.9
        self.assertIn(TaskPriority.MEDIUM, priorities)  # Score 0.7
        self.assertIn(TaskPriority.LOW, priorities)  # Score 0.5
        
        # Verify metadata
        self.assertEqual(result.metadata['tasks_generated'], 3)
        self.assertEqual(result.metadata['evidence_items_used'], 3)
        self.assertTrue(result.metadata['project_created'])
    
    def test_workflow_without_evidence(self):
        """Test workflow without evidence (no tasks generated)."""
        hypothesis = HypothesisProposal(
            title="Simple Hypothesis",
            description="Simple hypothesis without evidence",
            source_message_id="msg_002",
            pareto_score=0.6,
            created_at=self.now,
            created_by="researcher",
            status=HypothesisStatus.PENDING,
            metadata={}
        )
        
        result = self.bridge.create_project_from_hypothesis(
            hypothesis_id="hyp_002",
            hypothesis=hypothesis,
            created_by="test_user"
        )
        
        # Verify project created but no tasks
        self.assertIsInstance(result.project, AuraProject)
        self.assertEqual(len(result.tasks), 0)
        self.assertEqual(result.metadata['tasks_generated'], 0)
        self.assertEqual(result.metadata['evidence_items_used'], 0)
    
    def test_error_handling_invalid_status(self):
        """Test error handling for invalid hypothesis status."""
        hypothesis = HypothesisProposal(
            title="Rejected Hypothesis",
            description="This hypothesis was rejected",
            source_message_id="msg_003",
            pareto_score=0.3,
            created_at=self.now,
            created_by="researcher",
            status=HypothesisStatus.REJECTED,  # Invalid status
            metadata={}
        )
        
        with self.assertRaises(ValueError) as context:
            self.bridge.create_project_from_hypothesis(
                hypothesis_id="hyp_003",
                hypothesis=hypothesis,
                created_by="test_user"
            )
        
        self.assertIn("not valid for project creation", str(context.exception))
        self.assertIn("rejected", str(context.exception))


def main():
    """Run all tests."""
    print("Running Aura bridge tests...")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    test_classes = [
        TestAuraProject,
        TestAuraTask,
        TestTaskGenerator,
        TestAuraBridge,
        TestConvenienceFunction,
        TestIntegrationScenarios
    ]
    
    for test_class in test_classes:
        suite.addTest(unittest.TestLoader().loadTestsFromTestCase(test_class))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    if result.wasSuccessful():
        print("\n🎉 All Aura bridge tests passed!")
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        for failure in result.failures:
            print(f"FAIL: {failure[0]}")
            print(failure[1])
        for error in result.errors:
            print(f"ERROR: {error[0]}")
            print(error[1])
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)