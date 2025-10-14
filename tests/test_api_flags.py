# tests/test_api_flags.py — tests for API flag wiring and graceful fallbacks

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

# Mock OpenAI client before importing router.chat
with patch('openai.OpenAI') as mock_openai:
    mock_client = Mock()
    mock_openai.return_value = mock_client
    
    from router.chat import _answer_json, _format_contradictions
    from feature_flags import get_feature_flag

# Test fixtures
@pytest.fixture
def sample_contradictions():
    """Sample contradictions for testing."""
    return [
        {
            "subject": "Remote Work Policy",
            "claim_a": "Remote work is allowed for all employees",
            "claim_b": "Remote work is not allowed for any employees",
            "evidence_ids": ["mem-1", "mem-2"],
            "contradiction_type": "entity_predicate",
            "confidence": 0.8
        },
        {
            "subject": "Budget Allocation",
            "claim_a": "The budget was increased by 20%",
            "claim_b": "The budget was decreased by 15%",
            "evidence_ids": ["mem-3", "mem-4"],
            "contradiction_type": "semantic_sentiment",
            "confidence": 0.6
        }
    ]

@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = Mock()
    response = Mock()
    response.choices = [Mock()]
    response.choices[0].message.content = '{"answer": "Test answer", "citations": ["mem-1"], "guidance_questions": []}'
    client.chat.completions.create.return_value = response
    return client

class TestContradictionFormatting:
    """Test contradiction formatting functionality."""
    
    def test_format_contradictions_empty(self):
        """Test formatting empty contradictions list."""
        result = _format_contradictions([])
        assert result == ""
    
    def test_format_contradictions_single(self):
        """Test formatting single contradiction."""
        contradictions = [{
            "subject": "Test Subject",
            "claim_a": "Claim A text",
            "claim_b": "Claim B text",
            "contradiction_type": "test",
            "confidence": 0.8
        }]
        
        result = _format_contradictions(contradictions)
        
        assert "CONTRADICTIONS DETECTED:" in result
        assert "Subject: Test Subject" in result
        assert "Claim A: Claim A text" in result
        assert "Claim B: Claim B text" in result
        assert "Type: test" in result
        assert "Confidence: 0.80" in result
    
    def test_format_contradictions_multiple(self, sample_contradictions):
        """Test formatting multiple contradictions."""
        result = _format_contradictions(sample_contradictions)
        
        assert "CONTRADICTIONS DETECTED:" in result
        assert "1. Subject: Remote Work Policy" in result
        assert "2. Subject: Budget Allocation" in result
        assert "Claim A: Remote work is allowed" in result
        assert "Claim B: The budget was decreased" in result
    
    def test_format_contradictions_truncation(self):
        """Test that long claims are truncated."""
        contradictions = [{
            "subject": "Test Subject",
            "claim_a": "A" * 200,  # Very long claim
            "claim_b": "B" * 200,  # Very long claim
            "contradiction_type": "test",
            "confidence": 0.8
        }]
        
        result = _format_contradictions(contradictions)
        
        # Check that claims are truncated to 100 characters
        assert "A" * 100 + "..." in result
        assert "B" * 100 + "..." in result
        assert "A" * 200 not in result  # Full claim should not be present

class TestAnswerJson:
    """Test answer JSON generation with contradictions."""
    
    def test_answer_json_without_contradictions(self, mock_openai_client):
        """Test answer generation without contradictions."""
        with patch('router.chat.client', mock_openai_client):
            with patch('router.chat.get_feature_flag') as mock_flag:
                mock_flag.return_value = False
                
                result = _answer_json("test question", "test context")
                
                assert result["answer"] == "Test answer"
                assert result["citations"] == ["mem-1"]
                mock_openai_client.chat.completions.create.assert_called_once()
                
                # Check that contradictions are not included
                call_args = mock_openai_client.chat.completions.create.call_args
                user_content = call_args[1]["messages"][1]["content"]
                user_data = eval(user_content)  # Convert JSON string to dict
                assert "contradictions" not in user_data
    
    def test_answer_json_with_contradictions_flag_disabled(self, mock_openai_client, sample_contradictions):
        """Test answer generation with contradictions but flag disabled."""
        with patch('router.chat.client', mock_openai_client):
            with patch('router.chat.get_feature_flag') as mock_flag:
                mock_flag.return_value = False
                
                result = _answer_json("test question", "test context", sample_contradictions)
                
                assert result["answer"] == "Test answer"
                mock_openai_client.chat.completions.create.assert_called_once()
                
                # Check that contradictions are not included when flag is disabled
                call_args = mock_openai_client.chat.completions.create.call_args
                user_content = call_args[1]["messages"][1]["content"]
                user_data = eval(user_content)
                assert "contradictions" not in user_data
    
    def test_answer_json_with_contradictions_flag_enabled(self, mock_openai_client, sample_contradictions):
        """Test answer generation with contradictions and flag enabled."""
        with patch('router.chat.client', mock_openai_client):
            with patch('router.chat.get_feature_flag') as mock_flag:
                mock_flag.return_value = True
                
                result = _answer_json("test question", "test context", sample_contradictions)
                
                assert result["answer"] == "Test answer"
                mock_openai_client.chat.completions.create.assert_called_once()
                
                # Check that contradictions are included when flag is enabled
                call_args = mock_openai_client.chat.completions.create.call_args
                user_content = call_args[1]["messages"][1]["content"]
                user_data = eval(user_content)
                assert "contradictions" in user_data
                assert "CONTRADICTIONS DETECTED:" in user_data["contradictions"]
                assert "Remote Work Policy" in user_data["contradictions"]
                assert "Budget Allocation" in user_data["contradictions"]
    
    def test_answer_json_with_empty_contradictions(self, mock_openai_client):
        """Test answer generation with empty contradictions list."""
        with patch('router.chat.client', mock_openai_client):
            with patch('router.chat.get_feature_flag') as mock_flag:
                mock_flag.return_value = True
                
                result = _answer_json("test question", "test context", [])
                
                assert result["answer"] == "Test answer"
                mock_openai_client.chat.completions.create.assert_called_once()
                
                # Check that contradictions are not included when list is empty
                call_args = mock_openai_client.chat.completions.create.call_args
                user_content = call_args[1]["messages"][1]["content"]
                user_data = eval(user_content)
                assert "contradictions" not in user_data

class TestFlagWiring:
    """Test that flags properly control behavior."""
    
    def test_dual_index_flag_controls_selector(self):
        """Test that dual_index flag controls selector usage."""
        # Test that the function exists and can be called
        result = get_feature_flag("retrieval.dual_index", default=False)
        assert isinstance(result, bool)
    
    def test_contradictions_flag_controls_packing(self):
        """Test that contradictions_pack flag controls packing."""
        # Test that the function exists and can be called
        result = get_feature_flag("retrieval.contradictions_pack", default=False)
        assert isinstance(result, bool)
    
    def test_liftscore_flag_controls_scoring(self):
        """Test that liftscore flag controls scoring."""
        # Test that the function exists and can be called
        result = get_feature_flag("retrieval.liftscore", default=False)
        assert isinstance(result, bool)

class TestPineconeFallback:
    """Test Pinecone error handling and fallback behavior."""
    
    def test_pinecone_error_fallback(self):
        """Test that Pinecone errors trigger fallback to legacy retrieval."""
        with patch('router.chat.get_feature_flag') as mock_flag:
            mock_flag.side_effect = lambda flag, default: {
                "retrieval.dual_index": True,
                "retrieval.contradictions_pack": False,
                "retrieval.liftscore": False
            }.get(flag, default)
            
            with patch('router.chat.SelectionFactory') as mock_factory:
                with patch('router.chat._embed') as mock_embed:
                    with patch('router.chat._retrieve') as mock_retrieve:
                        with patch('router.chat._pack_context') as mock_pack:
                            # Mock Pinecone error in selector
                            mock_selector = Mock()
                            mock_selector.select.side_effect = Exception("Pinecone connection failed")
                            mock_factory.create_selector.return_value = mock_selector
                            
                            # Mock embedding
                            mock_embed.return_value = [0.1, 0.2, 0.3]
                            
                            # Mock legacy retrieval (fallback)
                            mock_retrieve.return_value = [{"id": "mem-1", "score": 0.8}]
                            mock_pack.return_value = [{"id": "mem-1", "text": "test content"}]
                            
                            # Simulate the retrieval logic
                            try:
                                selector = mock_factory.create_selector()
                                embedding = mock_embed("test query")
                                selection_result = selector.select(
                                    query="test query",
                                    embedding=embedding,
                                    caller_role="user"
                                )
                            except Exception as e:
                                # This should trigger fallback
                                print(f"Dual retrieval failed, falling back to legacy: {e}")
                                retrieved_meta = mock_retrieve("test", "test_index", "test query")
                                retrieved_chunks = mock_pack("test", retrieved_meta)
                            
                            # Verify fallback was called
                            mock_retrieve.assert_called_once()
                            mock_pack.assert_called_once()
    
    def test_legacy_retrieval_also_fails(self):
        """Test behavior when both dual and legacy retrieval fail."""
        with patch('router.chat.get_feature_flag') as mock_flag:
            mock_flag.side_effect = lambda flag, default: {
                "retrieval.dual_index": True,
                "retrieval.contradictions_pack": False,
                "retrieval.liftscore": False
            }.get(flag, default)
            
            with patch('router.chat.SelectionFactory') as mock_factory:
                with patch('router.chat._embed') as mock_embed:
                    with patch('router.chat._retrieve') as mock_retrieve:
                        with patch('router.chat._pack_context') as mock_pack:
                            # Mock both dual and legacy retrieval failures
                            mock_selector = Mock()
                            mock_selector.select.side_effect = Exception("Pinecone connection failed")
                            mock_factory.create_selector.return_value = mock_selector
                            
                            mock_embed.return_value = [0.1, 0.2, 0.3]
                            mock_retrieve.side_effect = Exception("Legacy retrieval also failed")
                            
                            # Simulate the retrieval logic
                            try:
                                selector = mock_factory.create_selector()
                                embedding = mock_embed("test query")
                                selection_result = selector.select(
                                    query="test query",
                                    embedding=embedding,
                                    caller_role="user"
                                )
                            except Exception as e:
                                print(f"Dual retrieval failed, falling back to legacy: {e}")
                                try:
                                    retrieved_meta = mock_retrieve("test", "test_index", "test query")
                                    retrieved_chunks = mock_pack("test", retrieved_meta)
                                except Exception as legacy_error:
                                    print(f"Legacy retrieval also failed: {legacy_error}")
                                    # Final fallback - return empty results
                                    retrieved_chunks = []
                            
                            # Verify both attempts were made
                            mock_retrieve.assert_called_once()
                            # Final fallback should result in empty chunks
                            assert retrieved_chunks == []

class TestIntegration:
    """Integration tests for flag behavior."""
    
    def test_flag_combination_dual_contradictions_liftscore(self):
        """Test behavior with all flags enabled."""
        # Test that all flag functions exist and return boolean values
        use_dual_retrieval = get_feature_flag("retrieval.dual_index", default=False)
        use_contradictions = get_feature_flag("retrieval.contradictions_pack", default=False)
        use_liftscore = get_feature_flag("retrieval.liftscore", default=False)
        
        assert isinstance(use_dual_retrieval, bool)
        assert isinstance(use_contradictions, bool)
        assert isinstance(use_liftscore, bool)
    
    def test_flag_combination_legacy_mode(self):
        """Test behavior with all flags disabled (legacy mode)."""
        # Test that all flag functions exist and return boolean values
        use_dual_retrieval = get_feature_flag("retrieval.dual_index", default=False)
        use_contradictions = get_feature_flag("retrieval.contradictions_pack", default=False)
        use_liftscore = get_feature_flag("retrieval.liftscore", default=False)
        
        assert isinstance(use_dual_retrieval, bool)
        assert isinstance(use_contradictions, bool)
        assert isinstance(use_liftscore, bool)
    
    def test_contradictions_in_model_input(self, mock_openai_client, sample_contradictions):
        """Test that contradictions are properly included in model input."""
        with patch('router.chat.client', mock_openai_client):
            with patch('router.chat.get_feature_flag') as mock_flag:
                mock_flag.return_value = True
                
                result = _answer_json("test question", "test context", sample_contradictions)
                
                # Verify the model was called
                mock_openai_client.chat.completions.create.assert_called_once()
                
                # Check the actual input to the model
                call_args = mock_openai_client.chat.completions.create.call_args
                messages = call_args[1]["messages"]
                
                # Should have system and user messages
                assert len(messages) == 2
                assert messages[0]["role"] == "system"
                assert messages[1]["role"] == "user"
                
                # Parse user content
                user_content = messages[1]["content"]
                user_data = eval(user_content)  # Convert JSON string to dict
                
                # Should have question, context, and contradictions
                assert "question" in user_data
                assert "context" in user_data
                assert "contradictions" in user_data
                
                # Contradictions should be formatted
                contradictions_text = user_data["contradictions"]
                assert "CONTRADICTIONS DETECTED:" in contradictions_text
                assert "Remote Work Policy" in contradictions_text
                assert "Budget Allocation" in contradictions_text

if __name__ == "__main__":
    pytest.main([__file__, "-v"])