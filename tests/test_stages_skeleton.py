"""
Tests for stage skeleton implementations.
"""

import json
import time
import sys
from typing import Dict, Any, List

# Add workspace to path
sys.path.insert(0, '/workspace')

from core.types import StageInput, StageOutput, StageMetrics, QueryContext
from core.orchestrator.stages import observe_stage, expand_stage, contrast_stage, order_stage


class TestStageFixtures:
    """Test fixtures for stage testing."""
    
    @staticmethod
    def create_sample_retrieval_results() -> List[Dict[str, Any]]:
        """Create sample retrieval results for testing."""
        return [
            {
                "id": "result_1",
                "title": "Machine Learning Basics",
                "text": "Machine learning is a subset of artificial intelligence that focuses on algorithms.",
                "score": 0.9,
                "type": "semantic",
                "metadata": {"created_at": "2024-01-01", "source": "textbook"}
            },
            {
                "id": "result_2", 
                "title": "AI vs Machine Learning",
                "text": "Artificial intelligence is broader than machine learning, which is a specific approach.",
                "score": 0.8,
                "type": "semantic",
                "metadata": {"created_at": "2024-01-02", "source": "article"}
            },
            {
                "id": "result_3",
                "title": "Deep Learning Tutorial",
                "text": "Deep learning uses neural networks with multiple layers to process data.",
                "score": 0.7,
                "type": "procedural",
                "metadata": {"created_at": "2024-01-03", "source": "tutorial"}
            },
            {
                "id": "result_4",
                "title": "Machine Learning in 2024",
                "text": "Machine learning has evolved significantly in 2024 with new techniques.",
                "score": 0.6,
                "type": "episodic",
                "metadata": {"created_at": "2024-01-04", "source": "news"}
            },
            {
                "id": "result_5",
                "title": "Contradictory ML Information",
                "text": "Machine learning is not a subset of artificial intelligence.",
                "score": 0.5,
                "type": "semantic",
                "metadata": {"created_at": "2024-01-05", "source": "blog"}
            }
        ]
    
    @staticmethod
    def create_sample_stage_input(query: str = "What is machine learning?") -> StageInput:
        """Create sample stage input for testing."""
        return StageInput(
            query=query,
            context={},
            retrieval_results=TestStageFixtures.create_sample_retrieval_results(),
            previous_stage_output=None,
            metadata={}
        )
    
    @staticmethod
    def create_observe_output() -> Dict[str, Any]:
        """Create sample observe stage output."""
        return {
            "query_analysis": {
                "length": 25,
                "word_count": 4,
                "complexity": 0.6,
                "question_type": "what",
                "entities": ["machine", "learning"],
                "keywords": ["machine", "learning"]
            },
            "retrieval_analysis": {
                "count": 5,
                "quality_score": 0.7,
                "coverage": 0.5,
                "relevance_scores": [0.9, 0.8, 0.7, 0.6, 0.5],
                "source_types": ["semantic", "procedural", "episodic"]
            },
            "intent_analysis": {
                "type": "what",
                "confidence": 0.8,
                "requires_detailed_answer": True,
                "requires_sources": True,
                "urgency": "medium"
            },
            "available_sources": 5,
            "context_quality": "good"
        }
    
    @staticmethod
    def create_expand_output() -> Dict[str, Any]:
        """Create sample expand stage output."""
        return {
            "original_results": 5,
            "expanded_results": 8,
            "related_concepts": [
                {"name": "artificial intelligence", "source": "result_1", "relevance": 0.9, "type": "concept"},
                {"name": "algorithms", "source": "result_1", "relevance": 0.8, "type": "concept"},
                {"name": "neural networks", "source": "result_3", "relevance": 0.7, "type": "concept"}
            ],
            "coverage_gaps": ["Missing context for keyword: algorithms"],
            "expansion_quality": "good",
            "expanded_sources": TestStageFixtures.create_sample_retrieval_results() + [
                {
                    "id": "expanded_artificial_intelligence",
                    "title": "Related to artificial intelligence",
                    "text": "Additional context related to artificial intelligence",
                    "score": 0.72,
                    "type": "expanded",
                    "source": "result_1",
                    "metadata": {"concept": "artificial intelligence", "expansion_type": "related_concept"}
                }
            ]
        }
    
    @staticmethod
    def create_contrast_output() -> Dict[str, Any]:
        """Create sample contrast stage output."""
        return {
            "contradictions": [
                {
                    "type": "factual_contradiction",
                    "subject": "machine learning",
                    "claim_a": "Machine learning is a subset of artificial intelligence...",
                    "claim_b": "Machine learning is not a subset of artificial intelligence...",
                    "source_a": "result_1",
                    "source_b": "result_5",
                    "severity": "high",
                    "confidence": 0.6
                }
            ],
            "conflict_patterns": [
                {"type": "repeated_factual_contradiction", "count": 1, "description": "Multiple factual_contradiction detected"}
            ],
            "severity_assessment": {
                "overall_severity": "high",
                "high_severity_count": 1,
                "medium_severity_count": 0,
                "low_severity_count": 0,
                "total_count": 1,
                "requires_attention": True,
                "confidence": 0.6
            },
            "total_contradictions": 1,
            "high_severity_count": 1,
            "resolution_suggestions": ["Cross-reference factual claims from 1 conflicting sources"]
        }


class TestObserveStage:
    """Test observe stage functionality."""
    
    def test_observe_stage_basic(self):
        """Test basic observe stage functionality."""
        print("Testing observe stage basic functionality...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        output = observe_stage(stage_input)
        
        # Check output structure
        assert isinstance(output, StageOutput)
        assert isinstance(output.result, dict)
        assert isinstance(output.metrics, StageMetrics)
        assert isinstance(output.reason, str)
        assert isinstance(output.warnings, list)
        assert isinstance(output.errors, list)
        
        # Check required fields in result
        assert "query_analysis" in output.result
        assert "retrieval_analysis" in output.result
        assert "intent_analysis" in output.result
        assert "available_sources" in output.result
        assert "context_quality" in output.result
        
        # Check metrics
        assert output.metrics.duration_ms > 0
        assert output.metrics.tokens_processed > 0
        
        print("✓ Observe stage basic functionality works")
    
    def test_observe_stage_query_analysis(self):
        """Test query analysis functionality."""
        print("Testing observe stage query analysis...")
        
        # Test different query types
        test_cases = [
            ("What is machine learning?", "what"),
            ("How does machine learning work?", "how"),
            ("Why is machine learning important?", "why"),
            ("Machine learning is important", "statement"),
        ]
        
        for query, expected_type in test_cases:
            stage_input = TestStageFixtures.create_sample_stage_input(query)
            output = observe_stage(stage_input)
            
            query_analysis = output.result["query_analysis"]
            assert query_analysis["question_type"] == expected_type
            assert query_analysis["length"] > 0
            assert query_analysis["word_count"] > 0
            assert 0.0 <= query_analysis["complexity"] <= 1.0
        
        print("✓ Observe stage query analysis works")
    
    def test_observe_stage_retrieval_analysis(self):
        """Test retrieval analysis functionality."""
        print("Testing observe stage retrieval analysis...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        output = observe_stage(stage_input)
        
        retrieval_analysis = output.result["retrieval_analysis"]
        assert retrieval_analysis["count"] == 5
        assert retrieval_analysis["quality_score"] > 0
        assert retrieval_analysis["coverage"] > 0
        assert len(retrieval_analysis["relevance_scores"]) == 5
        assert len(retrieval_analysis["source_types"]) > 0
        
        print("✓ Observe stage retrieval analysis works")
    
    def test_observe_stage_intent_analysis(self):
        """Test intent analysis functionality."""
        print("Testing observe stage intent analysis...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        output = observe_stage(stage_input)
        
        intent_analysis = output.result["intent_analysis"]
        assert intent_analysis["type"] in ["what", "how", "why", "when", "where", "who", "which", "question", "statement"]
        assert 0.0 <= intent_analysis["confidence"] <= 1.0
        assert isinstance(intent_analysis["requires_detailed_answer"], bool)
        assert isinstance(intent_analysis["requires_sources"], bool)
        assert intent_analysis["urgency"] in ["low", "medium", "high"]
        
        print("✓ Observe stage intent analysis works")
    
    def test_observe_stage_error_handling(self):
        """Test observe stage error handling."""
        print("Testing observe stage error handling...")
        
        # Test with empty input
        empty_input = StageInput(query="", retrieval_results=[])
        output = observe_stage(empty_input)
        
        assert isinstance(output, StageOutput)
        assert output.metrics.duration_ms > 0
        
        print("✓ Observe stage error handling works")


class TestExpandStage:
    """Test expand stage functionality."""
    
    def test_expand_stage_basic(self):
        """Test basic expand stage functionality."""
        print("Testing expand stage basic functionality...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        
        output = expand_stage(stage_input)
        
        # Check output structure
        assert isinstance(output, StageOutput)
        assert isinstance(output.result, dict)
        assert isinstance(output.metrics, StageMetrics)
        assert isinstance(output.reason, str)
        assert isinstance(output.warnings, list)
        assert isinstance(output.errors, list)
        
        # Check required fields in result
        assert "original_results" in output.result
        assert "expanded_results" in output.result
        assert "related_concepts" in output.result
        assert "coverage_gaps" in output.result
        assert "expansion_quality" in output.result
        assert "expanded_sources" in output.result
        
        print("✓ Expand stage basic functionality works")
    
    def test_expand_stage_concept_finding(self):
        """Test concept finding functionality."""
        print("Testing expand stage concept finding...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        
        output = expand_stage(stage_input)
        
        related_concepts = output.result["related_concepts"]
        assert isinstance(related_concepts, list)
        
        # Check concept structure
        for concept in related_concepts:
            assert "name" in concept
            assert "source" in concept
            assert "relevance" in concept
            assert "type" in concept
            assert 0.0 <= concept["relevance"] <= 1.0
        
        print("✓ Expand stage concept finding works")
    
    def test_expand_stage_expansion_quality(self):
        """Test expansion quality assessment."""
        print("Testing expand stage expansion quality...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        
        output = expand_stage(stage_input)
        
        expansion_quality = output.result["expansion_quality"]
        assert expansion_quality in ["excellent", "good", "fair", "poor"]
        
        original_count = output.result["original_results"]
        expanded_count = output.result["expanded_results"]
        assert expanded_count >= original_count
        
        print("✓ Expand stage expansion quality works")
    
    def test_expand_stage_coverage_gaps(self):
        """Test coverage gap identification."""
        print("Testing expand stage coverage gaps...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        
        output = expand_stage(stage_input)
        
        coverage_gaps = output.result["coverage_gaps"]
        assert isinstance(coverage_gaps, list)
        
        print("✓ Expand stage coverage gaps work")


class TestContrastStage:
    """Test contrast stage functionality."""
    
    def test_contrast_stage_basic(self):
        """Test basic contrast stage functionality."""
        print("Testing contrast stage basic functionality...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        
        output = contrast_stage(stage_input)
        
        # Check output structure
        assert isinstance(output, StageOutput)
        assert isinstance(output.result, dict)
        assert isinstance(output.metrics, StageMetrics)
        assert isinstance(output.reason, str)
        assert isinstance(output.warnings, list)
        assert isinstance(output.errors, list)
        
        # Check required fields in result
        assert "contradictions" in output.result
        assert "conflict_patterns" in output.result
        assert "severity_assessment" in output.result
        assert "total_contradictions" in output.result
        assert "high_severity_count" in output.result
        assert "resolution_suggestions" in output.result
        
        print("✓ Contrast stage basic functionality works")
    
    def test_contrast_stage_contradiction_detection(self):
        """Test contradiction detection functionality."""
        print("Testing contrast stage contradiction detection...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        
        output = contrast_stage(stage_input)
        
        contradictions = output.result["contradictions"]
        assert isinstance(contradictions, list)
        
        # Check contradiction structure
        for contradiction in contradictions:
            assert "type" in contradiction
            assert "subject" in contradiction
            assert "claim_a" in contradiction
            assert "claim_b" in contradiction
            assert "source_a" in contradiction
            assert "source_b" in contradiction
            assert "severity" in contradiction
            assert "confidence" in contradiction
            assert contradiction["severity"] in ["low", "medium", "high"]
            assert 0.0 <= contradiction["confidence"] <= 1.0
        
        print("✓ Contrast stage contradiction detection works")
    
    def test_contrast_stage_severity_assessment(self):
        """Test severity assessment functionality."""
        print("Testing contrast stage severity assessment...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        
        output = contrast_stage(stage_input)
        
        severity_assessment = output.result["severity_assessment"]
        assert "overall_severity" in severity_assessment
        assert "high_severity_count" in severity_assessment
        assert "medium_severity_count" in severity_assessment
        assert "low_severity_count" in severity_assessment
        assert "total_count" in severity_assessment
        assert "requires_attention" in severity_assessment
        assert "confidence" in severity_assessment
        
        assert severity_assessment["overall_severity"] in ["none", "low", "medium", "high"]
        assert isinstance(severity_assessment["requires_attention"], bool)
        assert 0.0 <= severity_assessment["confidence"] <= 1.0
        
        print("✓ Contrast stage severity assessment works")
    
    def test_contrast_stage_resolution_suggestions(self):
        """Test resolution suggestions functionality."""
        print("Testing contrast stage resolution suggestions...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        
        output = contrast_stage(stage_input)
        
        resolution_suggestions = output.result["resolution_suggestions"]
        assert isinstance(resolution_suggestions, list)
        
        print("✓ Contrast stage resolution suggestions work")


class TestOrderStage:
    """Test order stage functionality."""
    
    def test_order_stage_basic(self):
        """Test basic order stage functionality."""
        print("Testing order stage basic functionality...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        stage_input.context["contrast_analysis"] = TestStageFixtures.create_contrast_output()
        
        output = order_stage(stage_input)
        
        # Check output structure
        assert isinstance(output, StageOutput)
        assert isinstance(output.result, dict)
        assert isinstance(output.metrics, StageMetrics)
        assert isinstance(output.reason, str)
        assert isinstance(output.warnings, list)
        assert isinstance(output.errors, list)
        
        # Check required fields in result
        assert "priority_ranking" in output.result
        assert "topic_organization" in output.result
        assert "response_structure" in output.result
        assert "recommendations" in output.result
        assert "total_sources" in output.result
        assert "prioritized_sources" in output.result
        assert "contradictions_resolved" in output.result
        
        print("✓ Order stage basic functionality works")
    
    def test_order_stage_priority_ranking(self):
        """Test priority ranking functionality."""
        print("Testing order stage priority ranking...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        stage_input.context["contrast_analysis"] = TestStageFixtures.create_contrast_output()
        
        output = order_stage(stage_input)
        
        priority_ranking = output.result["priority_ranking"]
        assert isinstance(priority_ranking, list)
        assert len(priority_ranking) > 0
        
        # Check ranking structure
        for i, item in enumerate(priority_ranking):
            assert "result" in item
            assert "priority_score" in item
            assert "rank" in item
            assert 0.0 <= item["priority_score"] <= 1.0
            assert item["rank"] == i + 1
        
        # Check that ranking is sorted by priority score
        for i in range(len(priority_ranking) - 1):
            assert priority_ranking[i]["priority_score"] >= priority_ranking[i + 1]["priority_score"]
        
        print("✓ Order stage priority ranking works")
    
    def test_order_stage_topic_organization(self):
        """Test topic organization functionality."""
        print("Testing order stage topic organization...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        stage_input.context["contrast_analysis"] = TestStageFixtures.create_contrast_output()
        
        output = order_stage(stage_input)
        
        topic_organization = output.result["topic_organization"]
        assert isinstance(topic_organization, dict)
        
        # Check topic categories
        expected_categories = ["primary", "supporting", "background", "contradictory"]
        for category in expected_categories:
            assert category in topic_organization
            assert isinstance(topic_organization[category], list)
        
        print("✓ Order stage topic organization works")
    
    def test_order_stage_response_structure(self):
        """Test response structure functionality."""
        print("Testing order stage response structure...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        stage_input.context["contrast_analysis"] = TestStageFixtures.create_contrast_output()
        
        output = order_stage(stage_input)
        
        response_structure = output.result["response_structure"]
        assert "structure_type" in response_structure
        assert "sections" in response_structure
        assert "total_sections" in response_structure
        assert "complexity_level" in response_structure
        
        assert response_structure["structure_type"] in ["definitional", "procedural", "explanatory", "factual", "general"]
        assert isinstance(response_structure["sections"], list)
        assert response_structure["complexity_level"] in ["low", "medium", "high"]
        
        print("✓ Order stage response structure works")
    
    def test_order_stage_recommendations(self):
        """Test recommendations functionality."""
        print("Testing order stage recommendations...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        stage_input.previous_stage_output = TestStageFixtures.create_observe_output()
        stage_input.context["expanded_context"] = TestStageFixtures.create_expand_output()
        stage_input.context["contrast_analysis"] = TestStageFixtures.create_contrast_output()
        
        output = order_stage(stage_input)
        
        recommendations = output.result["recommendations"]
        assert isinstance(recommendations, list)
        
        # Check recommendation structure
        for recommendation in recommendations:
            assert "type" in recommendation
            assert "description" in recommendation
            assert "priority" in recommendation
            assert recommendation["priority"] in ["high", "medium", "low"]
        
        print("✓ Order stage recommendations work")


class TestStageSequencing:
    """Test stage sequencing and integration."""
    
    def test_stage_sequencing(self):
        """Test that stages can be chained together."""
        print("Testing stage sequencing...")
        
        # Start with observe stage
        stage_input = TestStageFixtures.create_sample_stage_input()
        observe_output = observe_stage(stage_input)
        
        # Pass observe output to expand stage
        stage_input.previous_stage_output = observe_output.result
        expand_output = expand_stage(stage_input)
        
        # Pass expand output to contrast stage
        stage_input.context["expanded_context"] = expand_output.result
        contrast_output = contrast_stage(stage_input)
        
        # Pass all outputs to order stage
        stage_input.previous_stage_output = observe_output.result
        stage_input.context["expanded_context"] = expand_output.result
        stage_input.context["contrast_analysis"] = contrast_output.result
        order_output = order_stage(stage_input)
        
        # Verify all stages executed successfully
        assert observe_output.errors == []
        assert expand_output.errors == []
        assert contrast_output.errors == []
        assert order_output.errors == []
        
        # Verify timing was captured
        assert observe_output.metrics.duration_ms > 0
        assert expand_output.metrics.duration_ms > 0
        assert contrast_output.metrics.duration_ms > 0
        assert order_output.metrics.duration_ms > 0
        
        print("✓ Stage sequencing works")
    
    def test_stage_timing_capture(self):
        """Test that timing is properly captured in all stages."""
        print("Testing stage timing capture...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        
        # Test each stage
        stages = [
            ("observe", observe_stage),
            ("expand", expand_stage),
            ("contrast", contrast_stage),
            ("order", order_stage),
        ]
        
        for stage_name, stage_func in stages:
            start_time = time.time()
            output = stage_func(stage_input)
            end_time = time.time()
            
            # Check that timing is reasonable
            actual_duration = (end_time - start_time) * 1000
            reported_duration = output.metrics.duration_ms
            
            # Allow some tolerance for timing differences
            assert abs(actual_duration - reported_duration) < 100, f"{stage_name} stage timing mismatch"
            assert reported_duration > 0, f"{stage_name} stage reported zero duration"
        
        print("✓ Stage timing capture works")
    
    def test_stage_output_feeding(self):
        """Test that stage outputs feed into next stages without exploding."""
        print("Testing stage output feeding...")
        
        stage_input = TestStageFixtures.create_sample_stage_input()
        
        # Run observe stage
        observe_output = observe_stage(stage_input)
        assert observe_output.errors == []
        
        # Feed observe output to expand stage
        stage_input.previous_stage_output = observe_output.result
        expand_output = expand_stage(stage_input)
        assert expand_output.errors == []
        
        # Feed expand output to contrast stage
        stage_input.context["expanded_context"] = expand_output.result
        contrast_output = contrast_stage(stage_input)
        assert contrast_output.errors == []
        
        # Feed all outputs to order stage
        stage_input.previous_stage_output = observe_output.result
        stage_input.context["expanded_context"] = expand_output.result
        stage_input.context["contrast_analysis"] = contrast_output.result
        order_output = order_stage(stage_input)
        assert order_output.errors == []
        
        print("✓ Stage output feeding works")


def main():
    """Run all stage tests."""
    print("Running stage skeleton tests...\n")
    
    try:
        # Test observe stage
        test_observe = TestObserveStage()
        test_observe.test_observe_stage_basic()
        test_observe.test_observe_stage_query_analysis()
        test_observe.test_observe_stage_retrieval_analysis()
        test_observe.test_observe_stage_intent_analysis()
        test_observe.test_observe_stage_error_handling()
        
        # Test expand stage
        test_expand = TestExpandStage()
        test_expand.test_expand_stage_basic()
        test_expand.test_expand_stage_concept_finding()
        test_expand.test_expand_stage_expansion_quality()
        test_expand.test_expand_stage_coverage_gaps()
        
        # Test contrast stage
        test_contrast = TestContrastStage()
        test_contrast.test_contrast_stage_basic()
        test_contrast.test_contrast_stage_contradiction_detection()
        test_contrast.test_contrast_stage_severity_assessment()
        test_contrast.test_contrast_stage_resolution_suggestions()
        
        # Test order stage
        test_order = TestOrderStage()
        test_order.test_order_stage_basic()
        test_order.test_order_stage_priority_ranking()
        test_order.test_order_stage_topic_organization()
        test_order.test_order_stage_response_structure()
        test_order.test_order_stage_recommendations()
        
        # Test stage sequencing
        test_sequencing = TestStageSequencing()
        test_sequencing.test_stage_sequencing()
        test_sequencing.test_stage_timing_capture()
        test_sequencing.test_stage_output_feeding()
        
        print("\n🎉 All stage skeleton tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())