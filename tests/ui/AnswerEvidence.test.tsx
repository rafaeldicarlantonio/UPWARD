/**
 * AnswerEvidence Component Tests
 * 
 * Comprehensive test suite for AnswerEvidence component including:
 * - Evidence anchor rendering
 * - Contradiction marker display
 * - Scroll functionality
 * - Accessibility
 * - Visual flagging of conflicts
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AnswerEvidence from '../../app/components/AnswerEvidence';
import { Contradiction } from '../../app/components/ContradictionBadge';

// ============================================================================
// Mock Data
// ============================================================================

const mockContentWithAnchors = `
  <p>According to the 2020 Census, New York City has a population of 
  <span id="evidence-1">8,336,817 residents</span>.</p>
  <p>However, some estimates suggest the population may be closer to 
  <span id="evidence-2">8.8 million</span> when including undocumented residents.</p>
  <p>The <span id="evidence-3">Census methodology</span> has been validated by 
  independent auditors.</p>
`;

const mockContradictions: Contradiction[] = [
  {
    id: 'c1',
    subject: 'Population count discrepancy',
    description: 'Census vs estimates show different numbers',
    evidenceAnchor: 'evidence-1',
    severity: 'high',
  },
  {
    id: 'c2',
    subject: 'Estimation methodology',
    description: 'Different counting methods produce different results',
    evidenceAnchor: 'evidence-2',
    severity: 'medium',
  },
];

const mockMultipleContradictionsForOneAnchor: Contradiction[] = [
  {
    id: 'c1',
    subject: 'First contradiction',
    description: 'Description 1',
    evidenceAnchor: 'evidence-1',
    severity: 'high',
  },
  {
    id: 'c2',
    subject: 'Second contradiction',
    description: 'Description 2',
    evidenceAnchor: 'evidence-1',
    severity: 'low',
  },
];

// ============================================================================
// Mock scroll functions
// ============================================================================

const mockScrollIntoView = jest.fn();

beforeEach(() => {
  Element.prototype.scrollIntoView = mockScrollIntoView;
});

afterEach(() => {
  jest.clearAllMocks();
});

// ============================================================================
// Tests
// ============================================================================

describe('AnswerEvidence', () => {
  // ==========================================================================
  // Basic Rendering Tests
  // ==========================================================================
  
  describe('Basic Rendering', () => {
    it('renders answer content', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      expect(screen.getByText(/8,336,817 residents/)).toBeInTheDocument();
      expect(screen.getByText(/8.8 million/)).toBeInTheDocument();
    });
    
    it('applies custom className', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
          className="custom-class"
        />
      );
      
      const element = screen.getByTestId('answer-evidence');
      expect(element).toHaveClass('custom-class');
    });
    
    it('sets data-has-contradictions attribute', () => {
      const { rerender } = render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      expect(screen.getByTestId('answer-evidence')).toHaveAttribute('data-has-contradictions', 'false');
      
      rerender(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      expect(screen.getByTestId('answer-evidence')).toHaveAttribute('data-has-contradictions', 'true');
    });
  });
  
  // ==========================================================================
  // Evidence Anchor Tests
  // ==========================================================================
  
  describe('Evidence Anchors', () => {
    it('adds data-evidence-anchor attribute to elements with IDs', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      const content = screen.getByTestId('answer-evidence');
      const anchor1 = content.querySelector('[data-evidence-anchor="evidence-1"]');
      const anchor2 = content.querySelector('[data-evidence-anchor="evidence-2"]');
      
      expect(anchor1).toBeInTheDocument();
      expect(anchor2).toBeInTheDocument();
    });
    
    it('adds evidence-anchor class to anchored elements', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      const content = screen.getByTestId('answer-evidence');
      const anchor = content.querySelector('[data-evidence-anchor="evidence-1"]');
      
      expect(anchor).toHaveClass('evidence-anchor');
    });
    
    it('preserves original element IDs', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      expect(document.getElementById('evidence-1')).toBeInTheDocument();
      expect(document.getElementById('evidence-2')).toBeInTheDocument();
      expect(document.getElementById('evidence-3')).toBeInTheDocument();
    });
  });
  
  // ==========================================================================
  // Contradiction Marker Tests
  // ==========================================================================
  
  describe('Contradiction Markers', () => {
    it('displays contradiction marker for evidence with conflicts', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      expect(screen.getByTestId('contradiction-marker-evidence-1')).toBeInTheDocument();
      expect(screen.getByTestId('contradiction-marker-evidence-2')).toBeInTheDocument();
    });
    
    it('does not display marker for evidence without conflicts', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      // evidence-3 has no contradictions
      expect(screen.queryByTestId('contradiction-marker-evidence-3')).not.toBeInTheDocument();
    });
    
    it('shows correct count in marker', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockMultipleContradictionsForOneAnchor}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveTextContent('2'); // 2 contradictions
    });
    
    it('displays severity icon in marker', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker1 = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker1).toHaveTextContent('⚠️'); // high severity
      
      const marker2 = screen.getByTestId('contradiction-marker-evidence-2');
      expect(marker2).toHaveTextContent('⚡'); // medium severity
    });
    
    it('uses highest severity when multiple contradictions', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockMultipleContradictionsForOneAnchor}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveTextContent('⚠️'); // high severity (highest of high and low)
    });
    
    it('includes tooltip with contradiction details', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      
      expect(marker).toHaveTextContent('Population count discrepancy');
      expect(marker).toHaveTextContent('Census vs estimates show different numbers');
    });
  });
  
  // ==========================================================================
  // Scroll Functionality Tests
  // ==========================================================================
  
  describe('Scroll Functionality', () => {
    it('scrolls to evidence when anchor clicked', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      const anchor = document.querySelector('[data-evidence-anchor="evidence-1"]') as HTMLElement;
      fireEvent.click(anchor);
      
      waitFor(() => {
        expect(mockScrollIntoView).toHaveBeenCalledWith({
          behavior: 'smooth',
          block: 'center',
        });
      });
    });
    
    it('calls onEvidenceClick callback when anchor clicked', () => {
      const onEvidenceClick = jest.fn();
      
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
          onEvidenceClick={onEvidenceClick}
        />
      );
      
      const anchor = document.querySelector('[data-evidence-anchor="evidence-1"]') as HTMLElement;
      fireEvent.click(anchor);
      
      waitFor(() => {
        expect(onEvidenceClick).toHaveBeenCalledWith('evidence-1');
      });
    });
    
    it('adds highlight animation class on scroll', () => {
      jest.useFakeTimers();
      
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      const anchor = document.querySelector('[data-evidence-anchor="evidence-1"]') as HTMLElement;
      fireEvent.click(anchor);
      
      waitFor(() => {
        expect(anchor).toHaveClass('evidence-highlight-active');
      });
      
      // Wait for animation to end
      jest.advanceTimersByTime(2000);
      
      waitFor(() => {
        expect(anchor).not.toHaveClass('evidence-highlight-active');
      });
      
      jest.useRealTimers();
    });
    
    it('handles hash navigation on mount', () => {
      // Mock window.location.hash
      Object.defineProperty(window, 'location', {
        writable: true,
        value: { hash: '#evidence-1' },
      });
      
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      waitFor(() => {
        expect(mockScrollIntoView).toHaveBeenCalled();
      }, { timeout: 200 });
    });
  });
  
  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================
  
  describe('Accessibility', () => {
    it('adds aria-label to contradiction markers', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveAttribute('aria-label', '1 contradiction(s)');
    });
    
    it('adds role="button" to contradiction markers', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveAttribute('role', 'button');
    });
    
    it('makes markers keyboard accessible with tabindex', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveAttribute('tabindex', '0');
    });
    
    it('adds role="tooltip" to tooltip element', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      const tooltip = marker.querySelector('[role="tooltip"]');
      
      expect(tooltip).toBeInTheDocument();
    });
    
    it('shows plural form for multiple contradictions', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockMultipleContradictionsForOneAnchor}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveTextContent('2 Contradictions');
    });
    
    it('shows singular form for one contradiction', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[mockContradictions[0]]}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveTextContent('1 Contradiction');
    });
  });
  
  // ==========================================================================
  // Visual Flagging Tests
  // ==========================================================================
  
  describe('Visual Flagging', () => {
    it('applies severity color to marker', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker1 = screen.getByTestId('contradiction-marker-evidence-1');
      const marker2 = screen.getByTestId('contradiction-marker-evidence-2');
      
      // Check CSS variable is set
      expect(marker1).toHaveStyle({ '--marker-color': '#dc3545' }); // high = red
      expect(marker2).toHaveStyle({ '--marker-color': '#ffc107' }); // medium = yellow
    });
    
    it('applies severity class to tooltip items', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      const tooltipItem = marker.querySelector('.tooltip-item');
      
      expect(tooltipItem).toHaveClass('severity-high');
    });
  });
  
  // ==========================================================================
  // Edge Cases Tests
  // ==========================================================================
  
  describe('Edge Cases', () => {
    it('handles content without anchors', () => {
      render(
        <AnswerEvidence
          content="<p>Simple content without any anchors</p>"
          contradictions={[]}
        />
      );
      
      expect(screen.getByText('Simple content without any anchors')).toBeInTheDocument();
    });
    
    it('handles empty contradictions array', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      expect(screen.queryByTestId(/contradiction-marker-/)).not.toBeInTheDocument();
    });
    
    it('handles contradictions without evidenceAnchor', () => {
      const contradictionsWithoutAnchor: Contradiction[] = [
        {
          id: 'c1',
          subject: 'General contradiction',
          description: 'No specific evidence anchor',
          severity: 'low',
        },
      ];
      
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={contradictionsWithoutAnchor}
        />
      );
      
      // Should not crash, and no markers should appear
      expect(screen.queryByTestId(/contradiction-marker-/)).not.toBeInTheDocument();
    });
    
    it('handles contradiction without description', () => {
      const contradictionsNoDesc: Contradiction[] = [
        {
          id: 'c1',
          subject: 'Subject only',
          evidenceAnchor: 'evidence-1',
          severity: 'medium',
        },
      ];
      
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={contradictionsNoDesc}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker).toHaveTextContent('Subject only');
      expect(marker).not.toHaveTextContent('undefined');
    });
  });
  
  // ==========================================================================
  // Acceptance Criteria Tests
  // ==========================================================================
  
  describe('Acceptance Criteria', () => {
    it('anchor links scroll correctly', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={[]}
        />
      );
      
      const anchor = document.querySelector('[data-evidence-anchor="evidence-1"]') as HTMLElement;
      fireEvent.click(anchor);
      
      waitFor(() => {
        expect(mockScrollIntoView).toHaveBeenCalledWith({
          behavior: 'smooth',
          block: 'center',
        });
      });
    });
    
    it('evidence with conflicts are visually flagged', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      // Check markers exist
      expect(screen.getByTestId('contradiction-marker-evidence-1')).toBeInTheDocument();
      expect(screen.getByTestId('contradiction-marker-evidence-2')).toBeInTheDocument();
      
      // Check visual indicators (icons and counts)
      const marker1 = screen.getByTestId('contradiction-marker-evidence-1');
      expect(marker1).toHaveTextContent('⚠️'); // Icon
      expect(marker1).toHaveTextContent('1'); // Count
      
      // Check no marker for evidence without conflicts
      expect(screen.queryByTestId('contradiction-marker-evidence-3')).not.toBeInTheDocument();
    });
    
    it('a11y labels provided', () => {
      render(
        <AnswerEvidence
          content={mockContentWithAnchors}
          contradictions={mockContradictions}
        />
      );
      
      const marker = screen.getByTestId('contradiction-marker-evidence-1');
      
      // Check ARIA attributes
      expect(marker).toHaveAttribute('aria-label');
      expect(marker).toHaveAttribute('role', 'button');
      expect(marker).toHaveAttribute('tabindex', '0');
      
      // Check tooltip role
      const tooltip = marker.querySelector('[role="tooltip"]');
      expect(tooltip).toBeInTheDocument();
    });
  });
});
