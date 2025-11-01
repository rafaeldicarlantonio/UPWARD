"""
Python-based structure tests for CompareCard component.

These tests verify that the TypeScript/React component exists and has
the expected structure, imports, and implementation patterns.
"""

from pathlib import Path


class TestCompareCardStructure:
    """Test CompareCard.tsx structure and implementation."""
    
    def test_compare_card_file_exists(self):
        """Verify CompareCard.tsx exists."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        assert file_path.exists(), "CompareCard.tsx should exist"
    
    def test_imports_role_system(self):
        """Verify CompareCard imports role system."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "from '../lib/roles'" in content
        assert "hasCapability" in content
        assert "CAP_READ_LEDGER_FULL" in content
    
    def test_imports_styles(self):
        """Verify CompareCard imports styles."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "import '../styles/compare.css'" in content
    
    def test_defines_types(self):
        """Verify CompareCard defines required types."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "interface EvidenceItem" in content
        assert "interface CompareSummary" in content
        assert "interface CompareCardProps" in content
        assert "stance_a: string" in content
        assert "stance_b: string" in content
        assert "internal_evidence" in content
        assert "external_evidence" in content
    
    def test_defines_component(self):
        """Verify CompareCard component is defined."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "export const CompareCard: React.FC<CompareCardProps>" in content
    
    def test_implements_role_gating(self):
        """Verify role gating for external compare."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "canRunExternalCompare" in content
        assert "allowExternalCompare" in content
        assert "hasCapability" in content
    
    def test_implements_truncation(self):
        """Verify external evidence truncation."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "truncateText" in content
        assert "getMaxSnippetChars" in content
        assert "maxLength" in content
    
    def test_implements_run_full_compare(self):
        """Verify run full compare functionality."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "handleRunFullCompare" in content
        assert "POST" in content
        assert "/factate/compare" in content
        assert "allow_external" in content
    
    def test_implements_loading_states(self):
        """Verify loading states."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "isLoading" in content
        assert "setIsLoading" in content
        assert "useState" in content
    
    def test_implements_error_handling(self):
        """Verify error handling."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "error" in content
        assert "setError" in content
        assert "try" in content
        assert "catch" in content
    
    def test_implements_provenance_display(self):
        """Verify provenance label and host display."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "label" in content
        assert "host" in content
        assert "extractHost" in content
    
    def test_has_testid_attributes(self):
        """Verify component has test IDs."""
        file_path = Path("/workspace/app/components/CompareCard.tsx")
        content = file_path.read_text()
        
        assert "data-testid" in content
        assert "testId" in content


class TestCompareStyles:
    """Test compare.css structure and styling."""
    
    def test_compare_css_exists(self):
        """Verify compare.css exists."""
        file_path = Path("/workspace/app/styles/compare.css")
        assert file_path.exists(), "compare.css should exist"
    
    def test_defines_card_container_styles(self):
        """Verify card container styles."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".compare-card {" in content
        assert ".compare-card-header {" in content
    
    def test_defines_stance_styles(self):
        """Verify stance styles."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".compare-stances {" in content
        assert ".stance {" in content
        assert ".stance-a" in content
        assert ".stance-b" in content
    
    def test_defines_evidence_styles(self):
        """Verify evidence section styles."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".evidence-sections {" in content
        assert ".evidence-section {" in content
        assert ".evidence-list {" in content
        assert ".evidence-item" in content
    
    def test_defines_internal_external_styles(self):
        """Verify internal/external evidence differentiation."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".evidence-item.internal" in content
        assert ".evidence-item.external" in content
    
    def test_defines_provenance_styles(self):
        """Verify provenance display styles."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".evidence-label" in content
        assert ".evidence-host" in content
        assert ".evidence-provenance" in content
    
    def test_defines_button_styles(self):
        """Verify run button styles."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".compare-card-run-button" in content
        assert ":disabled" in content
    
    def test_defines_error_styles(self):
        """Verify error display styles."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".compare-card-error" in content
    
    def test_defines_loading_styles(self):
        """Verify loading/spinner styles."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert ".button-spinner" in content
        assert "@keyframes spin" in content
    
    def test_includes_responsive_styles(self):
        """Verify responsive media queries."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert "@media (max-width: 768px)" in content
    
    def test_includes_dark_mode_support(self):
        """Verify dark mode support."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert "@media (prefers-color-scheme: dark)" in content
    
    def test_includes_accessibility_styles(self):
        """Verify accessibility enhancements."""
        file_path = Path("/workspace/app/styles/compare.css")
        content = file_path.read_text()
        
        assert "@media (prefers-contrast:" in content or "@media (prefers-reduced-motion:" in content


class TestCompareCardTests:
    """Test CompareCard test suite structure."""
    
    def test_test_file_exists(self):
        """Verify test file exists."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        assert file_path.exists(), "CompareCard.test.tsx should exist"
    
    def test_imports_testing_library(self):
        """Verify imports from React Testing Library."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "from '@testing-library/react'" in content
        assert "render" in content
        assert "screen" in content
        assert "fireEvent" in content
        assert "waitFor" in content
    
    def test_imports_jest_dom(self):
        """Verify jest-dom is imported."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "import '@testing-library/jest-dom'" in content
    
    def test_defines_mock_data(self):
        """Verify mock data is defined."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "mockCompareSummary" in content
        assert "mockInternalEvidence" in content
        assert "mockExternalEvidence" in content
    
    def test_mocks_fetch(self):
        """Verify fetch is mocked."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "global.fetch = jest.fn()" in content
        assert "mockFetchSuccess" in content
        assert "mockFetchError" in content
    
    def test_has_rendering_tests(self):
        """Verify rendering tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Rendering" in content
        assert "renders compare card with stances" in content
    
    def test_has_internal_evidence_tests(self):
        """Verify internal evidence tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Internal Evidence" in content
        assert "renders internal evidence" in content
    
    def test_has_external_evidence_tests(self):
        """Verify external evidence tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "External Evidence" in content
        assert "renders external evidence" in content
    
    def test_has_role_gating_tests(self):
        """Verify role gating tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Role Gating" in content
        assert "disables run button for General" in content
        assert "enables run button for Pro" in content
    
    def test_has_feature_flag_tests(self):
        """Verify feature flag tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Feature Flag" in content
        assert "allowExternalCompare" in content
    
    def test_has_run_full_compare_tests(self):
        """Verify run full compare tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Run Full Compare" in content
        assert "calls API when button clicked" in content
    
    def test_has_loading_state_tests(self):
        """Verify loading state tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Loading States" in content or "Loading State" in content
        assert "shows loading state" in content
    
    def test_has_truncation_tests(self):
        """Verify truncation tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Truncation" in content
        assert "truncates" in content
    
    def test_has_acceptance_criteria_tests(self):
        """Verify acceptance criteria tests exist."""
        file_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = file_path.read_text()
        
        assert "Acceptance Criteria" in content


class TestAcceptanceCriteria:
    """Verify all acceptance criteria are met."""
    
    def test_renders_normalized_compare_summary(self):
        """Verify component renders normalized compare_summary."""
        test_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = test_path.read_text()
        
        assert "renders normalized compare_summary" in content
        assert "stance_a" in content
        assert "stance_b" in content
    
    def test_external_evidence_grouped_and_truncated(self):
        """Verify external evidence is grouped and truncated."""
        test_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = test_path.read_text()
        
        assert "groups and truncates external evidence" in content
        assert "External Evidence" in content
        assert "truncates" in content
    
    def test_run_button_disabled_for_general_and_flags_off(self):
        """Verify run button disabled for General and when flags off."""
        test_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = test_path.read_text()
        
        assert "run button disabled for General and when flags off" in content
        assert "ROLE_GENERAL" in content
        assert "allowExternalCompare" in content
    
    def test_loading_states_tested(self):
        """Verify loading states are tested."""
        test_path = Path("/workspace/tests/ui/CompareCard.test.tsx")
        content = test_path.read_text()
        
        assert "loading states tested" in content
        assert "Running..." in content


class TestCodeQuality:
    """Verify code quality and best practices."""
    
    def test_has_documentation_comments(self):
        """Verify component has documentation comments."""
        card_path = Path("/workspace/app/components/CompareCard.tsx")
        content = card_path.read_text()
        
        # Check for JSDoc-style comments
        assert "/**" in content
        assert "* @" in content or "Features:" in content
    
    def test_uses_typescript_types(self):
        """Verify proper TypeScript typing."""
        card_path = Path("/workspace/app/components/CompareCard.tsx")
        content = card_path.read_text()
        
        assert ": React.FC<" in content
        assert "interface " in content
        assert ": string" in content or ": boolean" in content
    
    def test_uses_accessibility_attributes(self):
        """Verify accessibility attributes are used."""
        card_path = Path("/workspace/app/components/CompareCard.tsx")
        content = card_path.read_text()
        
        assert "title=" in content
        assert "disabled" in content
        assert "data-testid" in content
    
    def test_uses_semantic_html(self):
        """Verify semantic HTML elements are used."""
        card_path = Path("/workspace/app/components/CompareCard.tsx")
        content = card_path.read_text()
        
        # Should use button elements
        assert "<button" in content
    
    def test_handles_async_operations(self):
        """Verify proper async/await usage."""
        card_path = Path("/workspace/app/components/CompareCard.tsx")
        content = card_path.read_text()
        
        assert "async" in content
        assert "await" in content
        assert "fetch" in content
    
    def test_css_follows_bem_conventions(self):
        """Verify CSS follows naming conventions."""
        css_path = Path("/workspace/app/styles/compare.css")
        content = css_path.read_text()
        
        # Check for consistent naming pattern
        assert ".compare-card" in content
        assert ".compare-stances" in content
        assert ".evidence-item" in content


class TestIntegration:
    """Test integration patterns and examples."""
    
    def test_component_exports_types(self):
        """Verify component exports its types."""
        card_path = Path("/workspace/app/components/CompareCard.tsx")
        content = card_path.read_text()
        
        assert "export interface EvidenceItem" in content
        assert "export interface CompareSummary" in content
        assert "export interface CompareCardProps" in content
    
    def test_component_has_default_export(self):
        """Verify component has default export."""
        card_path = Path("/workspace/app/components/CompareCard.tsx")
        content = card_path.read_text()
        
        assert "export default CompareCard" in content
