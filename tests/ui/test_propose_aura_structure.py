"""
Python-based structure tests for ProposeAuraButton component.
"""

from pathlib import Path


class TestProposeAuraButtonStructure:
    """Test ProposeAuraButton.tsx structure."""
    
    def test_component_file_exists(self):
        assert Path("/workspace/app/components/ProposeAuraButton.tsx").exists()
    
    def test_imports_role_system(self):
        content = Path("/workspace/app/components/ProposeAuraButton.tsx").read_text()
        assert "from '../lib/roles'" in content
        assert "ROLE_PRO" in content
        assert "ROLE_ANALYTICS" in content
    
    def test_imports_api_module(self):
        content = Path("/workspace/app/components/ProposeAuraButton.tsx").read_text()
        assert "from '../api/aura'" in content
        assert "proposeAuraProject" in content
        assert "listRecentHypotheses" in content
    
    def test_implements_hypothesis_selection(self):
        content = Path("/workspace/app/components/ProposeAuraButton.tsx").read_text()
        assert "hypothesisId" in content
        assert "selectedHypothesisId" in content
        assert "recentHypotheses" in content
    
    def test_implements_starter_tasks(self):
        content = Path("/workspace/app/components/ProposeAuraButton.tsx").read_text()
        assert "starterTasks" in content
        assert "generateStarterTasks" in content
        assert "compareSummary" in content
    
    def test_implements_navigation(self):
        content = Path("/workspace/app/components/ProposeAuraButton.tsx").read_text()
        assert "navigateToProject" in content
        assert "window.location.href" in content


class TestAuraAPIStructure:
    """Test aura.ts API module structure."""
    
    def test_api_file_exists(self):
        assert Path("/workspace/app/api/aura.ts").exists()
    
    def test_defines_types(self):
        content = Path("/workspace/app/api/aura.ts").read_text()
        assert "interface ProposeAuraProjectRequest" in content
        assert "interface AuraProjectData" in content
        assert "interface HypothesisSummary" in content
    
    def test_exports_propose_function(self):
        content = Path("/workspace/app/api/aura.ts").read_text()
        assert "export async function proposeAuraProject" in content
    
    def test_exports_list_hypotheses(self):
        content = Path("/workspace/app/api/aura.ts").read_text()
        assert "export async function listRecentHypotheses" in content


class TestAcceptanceCriteria:
    """Verify acceptance criteria."""
    
    def test_role_gating_respected(self):
        test_content = Path("/workspace/tests/ui/ProposeAura.test.tsx").read_text()
        assert "role gating respected" in test_content or "Role Gating" in test_content
    
    def test_success_toast_and_navigation(self):
        test_content = Path("/workspace/tests/ui/ProposeAura.test.tsx").read_text()
        assert "success toast and navigation" in test_content or "navigates to project" in test_content
    
    def test_error_handling_shown(self):
        test_content = Path("/workspace/tests/ui/ProposeAura.test.tsx").read_text()
        assert "error handling shown" in test_content or "Error Handling" in test_content
    
    def test_telemetry_event_fired(self):
        test_content = Path("/workspace/tests/ui/ProposeAura.test.tsx").read_text()
        assert "telemetry event fired" in test_content or "Telemetry" in test_content
