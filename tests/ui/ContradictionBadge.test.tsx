/**
 * ContradictionBadge Component Tests
 * 
 * Comprehensive test suite for ContradictionBadge component including:
 * - Rendering with different counts
 * - Tooltip functionality
 * - Evidence anchor links and scrolling
 * - Feature flag compliance (alwaysShow)
 * - Severity levels
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ContradictionBadge, { Contradiction } from '../../app/components/ContradictionBadge';

// ============================================================================
// Mock Data
// ============================================================================

const mockContradictions: Contradiction[] = [
  {
    id: 'c1',
    subject: 'Population figures',
    description: 'Conflicting data about city population',
    evidenceAnchor: 'evidence-1',
    severity: 'medium',
    source: 'Census 2020 vs 2021 estimate',
  },
  {
    id: 'c2',
    subject: 'Historical dates',
    description: 'Two different dates given for the same event',
    evidenceAnchor: 'evidence-2',
    severity: 'low',
    source: 'Primary source A vs B',
  },
  {
    id: 'c3',
    subject: 'Scientific consensus',
    description: 'Statement contradicts established research',
    evidenceAnchor: 'evidence-3',
    severity: 'high',
    source: 'Peer-reviewed literature',
  },
];

const mockSingleContradiction: Contradiction[] = [
  {
    id: 'c1',
    subject: 'Temperature data',
    description: 'Conflicting temperature measurements',
    evidenceAnchor: 'temp-evidence',
    severity: 'low',
  },
];

const mockNoAnchorContradictions: Contradiction[] = [
  {
    id: 'c1',
    subject: 'General inconsistency',
    description: 'No specific evidence anchor',
    severity: 'low',
  },
];

// ============================================================================
// Helper Functions
// ============================================================================

function createMockElement(id: string): HTMLElement {
  const element = document.createElement('div');
  element.id = id;
  element.textContent = `Mock element ${id}`;
  document.body.appendChild(element);
  return element;
}

function cleanupMockElements(): void {
  document.querySelectorAll('[id^="evidence-"]').forEach(el => el.remove());
  document.querySelectorAll('[id^="temp-"]').forEach(el => el.remove());
}

// Mock scrollIntoView
Element.prototype.scrollIntoView = jest.fn();

// ============================================================================
// Test Setup
// ============================================================================

describe('ContradictionBadge', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    cleanupMockElements();
  });
  
  afterEach(() => {
    cleanupMockElements();
  });
  
  // ==========================================================================
  // Rendering Tests
  // ==========================================================================
  
  describe('Rendering', () => {
    it('renders badge with correct count', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('Contradictions: 3');
      expect(badge).toHaveAttribute('data-count', '3');
    });
    
    it('renders singular label for one contradiction', () => {
      render(<ContradictionBadge contradictions={mockSingleContradiction} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveAttribute('aria-label', '1 contradiction');
    });
    
    it('renders plural label for multiple contradictions', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveAttribute('aria-label', '3 contradictions');
    });
    
    it('hides when count is 0 and alwaysShow is false', () => {
      render(<ContradictionBadge contradictions={[]} alwaysShow={false} />);
      
      expect(screen.queryByTestId('contradiction-badge')).not.toBeInTheDocument();
    });
    
    it('shows when count is 0 and alwaysShow is true', () => {
      render(<ContradictionBadge contradictions={[]} alwaysShow={true} />);
      
      expect(screen.getByTestId('contradiction-badge')).toBeInTheDocument();
      expect(screen.getByText('Contradictions: 0')).toBeInTheDocument();
    });
    
    it('applies custom className', () => {
      render(
        <ContradictionBadge 
          contradictions={mockContradictions} 
          className="custom-class"
        />
      );
      
      const container = screen.getByTestId('contradiction-badge');
      expect(container).toHaveClass('custom-class');
    });
  });
  
  // ==========================================================================
  // Color and Icon Tests
  // ==========================================================================
  
  describe('Color and Icon', () => {
    it('uses success color when count is 0', () => {
      render(<ContradictionBadge contradictions={[]} alwaysShow={true} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveClass('badge-success');
    });
    
    it('uses success icon when count is 0', () => {
      render(<ContradictionBadge contradictions={[]} alwaysShow={true} />);
      
      expect(screen.getByText('✓')).toBeInTheDocument();
    });
    
    it('uses warning icon when count > 0', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      expect(screen.getByText('⚠')).toBeInTheDocument();
    });
    
    it('uses danger color for high severity contradictions', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveClass('badge-danger');
    });
    
    it('uses warning color for medium severity without high', () => {
      const mediumOnly = mockContradictions.filter(c => c.severity !== 'high');
      render(<ContradictionBadge contradictions={mediumOnly} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveClass('badge-warning');
    });
    
    it('uses info color for low severity only', () => {
      const lowOnly = mockContradictions.filter(c => c.severity === 'low');
      render(<ContradictionBadge contradictions={lowOnly} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveClass('badge-info');
    });
  });
  
  // ==========================================================================
  // Tooltip Tests
  // ==========================================================================
  
  describe('Tooltip', () => {
    it('shows tooltip on badge click', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      expect(screen.getByTestId('contradiction-badge-tooltip')).toBeInTheDocument();
      expect(screen.getByText('3 Contradictions Found')).toBeInTheDocument();
    });
    
    it('hides tooltip on second click', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      
      // Open
      fireEvent.click(badge);
      expect(screen.getByTestId('contradiction-badge-tooltip')).toBeInTheDocument();
      
      // Close
      fireEvent.click(badge);
      expect(screen.queryByTestId('contradiction-badge-tooltip')).not.toBeInTheDocument();
    });
    
    it('closes tooltip on close button click', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const closeButton = screen.getByTestId('contradiction-badge-tooltip-close');
      fireEvent.click(closeButton);
      
      expect(screen.queryByTestId('contradiction-badge-tooltip')).not.toBeInTheDocument();
    });
    
    it('closes tooltip on escape key', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      fireEvent.keyDown(document, { key: 'Escape' });
      
      expect(screen.queryByTestId('contradiction-badge-tooltip')).not.toBeInTheDocument();
    });
    
    it('closes tooltip on click outside', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      fireEvent.mouseDown(document.body);
      
      expect(screen.queryByTestId('contradiction-badge-tooltip')).not.toBeInTheDocument();
    });
    
    it('lists all contradictions in tooltip', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      expect(screen.getByText('Population figures')).toBeInTheDocument();
      expect(screen.getByText('Historical dates')).toBeInTheDocument();
      expect(screen.getByText('Scientific consensus')).toBeInTheDocument();
    });
    
    it('shows descriptions when available', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      expect(screen.getByText(/Conflicting data about city population/)).toBeInTheDocument();
    });
    
    it('shows sources when available', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      expect(screen.getByText(/Census 2020 vs 2021 estimate/)).toBeInTheDocument();
    });
    
    it('shows severity badges', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const severityBadges = screen.getAllByText(/low|medium|high/i);
      expect(severityBadges.length).toBeGreaterThan(0);
    });
    
    it('shows no contradictions message when count is 0', () => {
      render(<ContradictionBadge contradictions={[]} alwaysShow={true} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      expect(screen.getByText('No contradictions detected')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Evidence Link Tests
  // ==========================================================================
  
  describe('Evidence Links', () => {
    it('renders links for contradictions with evidence anchors', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const link = screen.getByTestId('contradiction-badge-link-0');
      expect(link).toHaveAttribute('href', '#evidence-1');
    });
    
    it('renders plain text for contradictions without evidence anchors', () => {
      render(<ContradictionBadge contradictions={mockNoAnchorContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      expect(screen.getByText('General inconsistency')).toBeInTheDocument();
      expect(screen.queryByTestId('contradiction-badge-link-0')).not.toBeInTheDocument();
    });
    
    it('scrolls to evidence anchor on link click', () => {
      const mockElement = createMockElement('evidence-1');
      
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const link = screen.getByTestId('contradiction-badge-link-0');
      fireEvent.click(link);
      
      expect(mockElement.scrollIntoView).toHaveBeenCalledWith({
        behavior: 'smooth',
        block: 'center',
      });
    });
    
    it('adds highlight class to evidence element', async () => {
      const mockElement = createMockElement('evidence-1');
      
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const link = screen.getByTestId('contradiction-badge-link-0');
      fireEvent.click(link);
      
      expect(mockElement.classList.contains('evidence-highlight')).toBe(true);
    });
    
    it('calls onEvidenceClick callback when link clicked', () => {
      const onEvidenceClick = jest.fn();
      
      createMockElement('evidence-1');
      render(
        <ContradictionBadge 
          contradictions={mockContradictions}
          onEvidenceClick={onEvidenceClick}
        />
      );
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const link = screen.getByTestId('contradiction-badge-link-0');
      fireEvent.click(link);
      
      expect(onEvidenceClick).toHaveBeenCalledWith('evidence-1');
    });
    
    it('closes tooltip after evidence link click', () => {
      createMockElement('evidence-1');
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const link = screen.getByTestId('contradiction-badge-link-0');
      fireEvent.click(link);
      
      expect(screen.queryByTestId('contradiction-badge-tooltip')).not.toBeInTheDocument();
    });
    
    it('handles missing evidence element gracefully', () => {
      // Don't create the element
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const link = screen.getByTestId('contradiction-badge-link-0');
      
      // Should not throw
      expect(() => fireEvent.click(link)).not.toThrow();
    });
  });
  
  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================
  
  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveAttribute('aria-label', '3 contradictions');
    });
    
    it('sets aria-expanded based on tooltip state', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveAttribute('aria-expanded', 'false');
      
      fireEvent.click(badge);
      expect(badge).toHaveAttribute('aria-expanded', 'true');
    });
    
    it('has role="tooltip" on tooltip element', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const tooltip = screen.getByRole('tooltip');
      expect(tooltip).toBeInTheDocument();
    });
    
    it('close button has aria-label', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const closeButton = screen.getByTestId('contradiction-badge-tooltip-close');
      expect(closeButton).toHaveAttribute('aria-label', 'Close tooltip');
    });
  });
  
  // ==========================================================================
  // Feature Flag Tests
  // ==========================================================================
  
  describe('Feature Flag Compliance', () => {
    it('respects alwaysShow=false when count is 0', () => {
      render(<ContradictionBadge contradictions={[]} alwaysShow={false} />);
      
      expect(screen.queryByTestId('contradiction-badge')).not.toBeInTheDocument();
    });
    
    it('respects alwaysShow=true when count is 0', () => {
      render(<ContradictionBadge contradictions={[]} alwaysShow={true} />);
      
      expect(screen.getByTestId('contradiction-badge')).toBeInTheDocument();
    });
    
    it('always shows when count > 0 regardless of alwaysShow', () => {
      const { rerender } = render(
        <ContradictionBadge contradictions={mockContradictions} alwaysShow={false} />
      );
      expect(screen.getByTestId('contradiction-badge')).toBeInTheDocument();
      
      rerender(
        <ContradictionBadge contradictions={mockContradictions} alwaysShow={true} />
      );
      expect(screen.getByTestId('contradiction-badge')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Severity Tests
  // ==========================================================================
  
  describe('Severity Levels', () => {
    it('applies severity class to items', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const item0 = screen.getByTestId('contradiction-badge-item-0');
      expect(item0).toHaveClass('severity-medium');
      
      const item1 = screen.getByTestId('contradiction-badge-item-1');
      expect(item1).toHaveClass('severity-low');
      
      const item2 = screen.getByTestId('contradiction-badge-item-2');
      expect(item2).toHaveClass('severity-high');
    });
    
    it('defaults to low severity when not specified', () => {
      const noSeverity: Contradiction[] = [
        {
          id: 'c1',
          subject: 'Test',
          evidenceAnchor: 'test',
        },
      ];
      
      render(<ContradictionBadge contradictions={noSeverity} />);
      
      const badge = screen.getByTestId('contradiction-badge-button');
      fireEvent.click(badge);
      
      const item = screen.getByTestId('contradiction-badge-item-0');
      expect(item).toHaveClass('severity-low');
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('renders count from response.contradictions', () => {
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      expect(screen.getByText('Contradictions: 3')).toBeInTheDocument();
    });
    
    it('links scroll to evidence', () => {
      const mockElement = createMockElement('evidence-1');
      
      render(<ContradictionBadge contradictions={mockContradictions} />);
      
      // Open tooltip
      fireEvent.click(screen.getByTestId('contradiction-badge-button'));
      
      // Click evidence link
      fireEvent.click(screen.getByTestId('contradiction-badge-link-0'));
      
      // Verify scroll was called
      expect(mockElement.scrollIntoView).toHaveBeenCalled();
    });
    
    it('hidden when N=0 unless alwaysShow forces always-on', () => {
      const { rerender } = render(
        <ContradictionBadge contradictions={[]} alwaysShow={false} />
      );
      
      // Hidden by default
      expect(screen.queryByTestId('contradiction-badge')).not.toBeInTheDocument();
      
      // Shown when forced
      rerender(<ContradictionBadge contradictions={[]} alwaysShow={true} />);
      expect(screen.getByTestId('contradiction-badge')).toBeInTheDocument();
    });
    
    it('color and icon change when N>0', () => {
      const { rerender } = render(
        <ContradictionBadge contradictions={[]} alwaysShow={true} />
      );
      
      // N=0: success color, checkmark icon
      let badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).toHaveClass('badge-success');
      expect(screen.getByText('✓')).toBeInTheDocument();
      
      // N>0: different color, warning icon
      rerender(<ContradictionBadge contradictions={mockSingleContradiction} />);
      badge = screen.getByTestId('contradiction-badge-button');
      expect(badge).not.toHaveClass('badge-success');
      expect(screen.getByText('⚠')).toBeInTheDocument();
    });
  });
});
