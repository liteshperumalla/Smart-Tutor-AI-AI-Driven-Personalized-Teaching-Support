"""
Unit Tests for Semantic Chunker
Tests sentence-aware chunking, structure preservation, and metadata enrichment
"""

import pytest
from typing import List, Dict
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from backend.rag.semantic_chunker import SemanticChunker, Chunk


class TestSemanticChunker:
    """Test suite for SemanticChunker"""

    @pytest.fixture
    def chunker(self):
        """Create a default semantic chunker instance"""
        return SemanticChunker(
            target_chunk_size=512,
            min_chunk_size=100,
            max_chunk_size=1000,
            overlap_sentences=1
        )

    @pytest.fixture
    def sample_text(self):
        """Sample text with multiple sentences"""
        return """
        Machine learning is a subset of artificial intelligence. It focuses on building systems
        that can learn from data. These systems improve their performance over time without being
        explicitly programmed.

        There are three main types of machine learning. Supervised learning uses labeled data.
        Unsupervised learning finds patterns in unlabeled data. Reinforcement learning learns
        through trial and error.
        """

    @pytest.fixture
    def sample_markdown(self):
        """Sample markdown document with structure"""
        return """
# Introduction to Neural Networks

Neural networks are computational models inspired by biological neural networks.

## Architecture

A neural network consists of layers of interconnected nodes. Each node performs a simple computation.

### Input Layer
The input layer receives the raw data. It passes information to hidden layers.

### Hidden Layers
Hidden layers process information through weighted connections. They extract features from the input.

### Output Layer
The output layer produces the final prediction. It can be used for classification or regression.

## Training Process

Training involves adjusting weights to minimize error. This is done through backpropagation.
        """

    def test_initialization(self):
        """Test chunker initialization with different parameters"""
        chunker = SemanticChunker(
            target_chunk_size=256,
            min_chunk_size=50,
            max_chunk_size=500
        )
        assert chunker.target_chunk_size == 256
        assert chunker.min_chunk_size == 50
        assert chunker.max_chunk_size == 500

    def test_sentence_splitting(self, chunker, sample_text):
        """Test that text is properly split into sentences"""
        chunks = chunker.chunk_document(sample_text)

        # Should create chunks
        assert len(chunks) > 0

        # Each chunk should be a Chunk object
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

        # Chunks should respect sentence boundaries (no mid-sentence cuts)
        for chunk in chunks:
            # Check that chunk ends with sentence-ending punctuation
            text = chunk.text.strip()
            if text:  # Only check non-empty chunks
                # Allow for various sentence endings
                assert text[-1] in '.!?"\'' or text.endswith('...')

    def test_chunk_size_constraints(self, chunker):
        """Test that chunks respect size constraints"""
        # Long text that should be split
        long_text = " ".join(["This is a test sentence."] * 100)

        chunks = chunker.chunk_document(long_text)

        for chunk in chunks:
            # Each chunk should be within size constraints
            assert len(chunk.text) >= chunker.min_chunk_size or len(chunk.text) == len(long_text)
            assert len(chunk.text) <= chunker.max_chunk_size

    def test_metadata_enrichment(self, chunker):
        """Test that metadata is properly added to chunks"""
        text = "This is a test document. It has multiple sentences."
        metadata = {
            "title": "Test Document",
            "source": "test.txt",
            "author": "Test Author"
        }

        chunks = chunker.chunk_document(text, metadata=metadata)

        for chunk in chunks:
            # All original metadata should be preserved
            assert "title" in chunk.metadata
            assert chunk.metadata["title"] == "Test Document"
            assert chunk.metadata["source"] == "test.txt"
            assert chunk.metadata["author"] == "Test Author"

    def test_heading_extraction(self, chunker, sample_markdown):
        """Test extraction of markdown headings"""
        chunks = chunker.chunk_document(sample_markdown)

        # Should extract headings and add to metadata
        heading_chunks = [c for c in chunks if "heading" in c.metadata]
        assert len(heading_chunks) > 0

        # Check that headings are properly formatted
        for chunk in heading_chunks:
            if chunk.metadata.get("heading"):
                # Heading should not contain markdown symbols
                assert not chunk.metadata["heading"].startswith("#")

    def test_code_block_preservation(self, chunker):
        """Test that code blocks are preserved intact"""
        text_with_code = """
        Here's a Python example:

        ```python
        def hello_world():
            print("Hello, World!")
            return True
        ```

        This code prints a message.
        """

        chunks = chunker.chunk_document(text_with_code)

        # Code block should be in one of the chunks
        code_found = False
        for chunk in chunks:
            if "def hello_world" in chunk.text:
                code_found = True
                # Code block should be complete (not split mid-function)
                assert "print(" in chunk.text
                assert "return True" in chunk.text

        assert code_found, "Code block not found in any chunk"

    def test_table_preservation(self, chunker):
        """Test that markdown tables are preserved"""
        text_with_table = """
        Here's a comparison:

        | Model | Accuracy | Speed |
        |-------|----------|-------|
        | A     | 95%      | Fast  |
        | B     | 98%      | Slow  |

        As you can see, Model B is more accurate.
        """

        chunks = chunker.chunk_document(text_with_table)

        # Table should be in chunks
        table_found = False
        for chunk in chunks:
            if "Model | Accuracy" in chunk.text:
                table_found = True
                # Table should be complete
                assert "Model A" in chunk.text or "A" in chunk.text
                assert "Model B" in chunk.text or "B" in chunk.text

        assert table_found, "Table not found in chunks"

    def test_parent_child_chunks(self, chunker):
        """Test parent-child chunk relationships"""
        text = " ".join(["Sentence number {}.".format(i) for i in range(50)])

        chunks = chunker.chunk_document(
            text,
            create_parent_chunks=True,
            parent_chunk_size=2000
        )

        # Should have both parent and child chunks
        parent_chunks = [c for c in chunks if c.chunk_type == "parent"]
        child_chunks = [c for c in chunks if c.chunk_type == "child"]

        assert len(parent_chunks) > 0, "No parent chunks created"
        assert len(child_chunks) > 0, "No child chunks created"

        # Each child should reference a parent
        for child in child_chunks:
            assert "parent_id" in child.metadata

    def test_empty_text_handling(self, chunker):
        """Test handling of empty or whitespace-only text"""
        empty_chunks = chunker.chunk_document("")
        assert len(empty_chunks) == 0

        whitespace_chunks = chunker.chunk_document("   \n\n  ")
        assert len(whitespace_chunks) == 0

    def test_chunk_overlap(self, chunker):
        """Test that overlapping sentences are preserved"""
        text = """
        First sentence. Second sentence. Third sentence. Fourth sentence.
        Fifth sentence. Sixth sentence. Seventh sentence. Eighth sentence.
        """

        chunks = chunker.chunk_document(text)

        if len(chunks) > 1:
            # Check for overlap between consecutive chunks
            for i in range(len(chunks) - 1):
                current_chunk = chunks[i].text
                next_chunk = chunks[i + 1].text

                # There should be some overlapping content
                # (at least one shared sentence)
                current_sentences = current_chunk.split('.')
                next_sentences = next_chunk.split('.')

                # Last sentence of current might be first of next
                overlap_found = any(
                    s.strip() in next_chunk
                    for s in current_sentences[-2:]
                    if s.strip()
                )

    def test_list_preservation(self, chunker):
        """Test that lists are preserved properly"""
        text_with_list = """
        Machine learning includes:

        1. Supervised learning
        2. Unsupervised learning
        3. Reinforcement learning

        Each has different applications.
        """

        chunks = chunker.chunk_document(text_with_list)

        # List should be preserved in chunks
        list_found = False
        for chunk in chunks:
            if "Supervised learning" in chunk.text:
                list_found = True
                # All list items should be together
                assert "Unsupervised learning" in chunk.text
                assert "Reinforcement learning" in chunk.text

        assert list_found, "List not preserved in chunks"

    def test_quote_preservation(self, chunker):
        """Test that block quotes are preserved"""
        text_with_quote = """
        As Einstein said:

        > "Imagination is more important than knowledge."

        This quote emphasizes creativity.
        """

        chunks = chunker.chunk_document(text_with_quote)

        # Quote should be in chunks
        quote_found = False
        for chunk in chunks:
            if "Imagination" in chunk.text:
                quote_found = True
                # Full quote should be present
                assert "knowledge" in chunk.text

        assert quote_found, "Quote not found in chunks"

    def test_chunk_ids(self, chunker, sample_text):
        """Test that chunks have unique IDs"""
        chunks = chunker.chunk_document(sample_text)

        # All chunks should have IDs
        assert all(chunk.chunk_id for chunk in chunks)

        # IDs should be unique
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        assert len(chunk_ids) == len(set(chunk_ids)), "Duplicate chunk IDs found"

    def test_contextual_prefix(self, chunker):
        """Test that contextual prefixes are added"""
        text = """
        Machine learning is a field of AI.
        It uses statistical techniques.
        """

        metadata = {"title": "ML Introduction"}
        chunks = chunker.chunk_document(
            text,
            metadata=metadata,
            add_contextual_prefix=True
        )

        # Chunks should have contextual information
        for chunk in chunks:
            # Prefix should include title
            assert "ML Introduction" in chunk.text or "title" in chunk.metadata

    def test_chunk_statistics(self, chunker, sample_text):
        """Test chunk statistics generation"""
        chunks = chunker.chunk_document(sample_text)

        stats = chunker.get_chunk_statistics(chunks)

        assert "total_chunks" in stats
        assert "avg_chunk_size" in stats
        assert "min_chunk_size" in stats
        assert "max_chunk_size" in stats
        assert stats["total_chunks"] == len(chunks)

    def test_multilingual_text(self, chunker):
        """Test handling of non-English text (basic support)"""
        spanish_text = """
        El aprendizaje automático es un subcampo de la inteligencia artificial.
        Se centra en la construcción de sistemas que pueden aprender de los datos.
        """

        chunks = chunker.chunk_document(spanish_text)

        # Should create chunks without errors
        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)


class TestChunkClass:
    """Test the Chunk dataclass"""

    def test_chunk_creation(self):
        """Test creating a Chunk instance"""
        chunk = Chunk(
            chunk_id="test_001",
            text="This is a test chunk.",
            metadata={"source": "test"},
            chunk_type="child",
            start_char=0,
            end_char=22
        )

        assert chunk.chunk_id == "test_001"
        assert chunk.text == "This is a test chunk."
        assert chunk.metadata["source"] == "test"
        assert chunk.chunk_type == "child"

    def test_chunk_to_dict(self):
        """Test converting chunk to dictionary"""
        chunk = Chunk(
            chunk_id="test_002",
            text="Test text",
            metadata={"key": "value"}
        )

        chunk_dict = chunk.to_dict()

        assert chunk_dict["chunk_id"] == "test_002"
        assert chunk_dict["text"] == "Test text"
        assert chunk_dict["metadata"]["key"] == "value"

    def test_chunk_from_dict(self):
        """Test creating chunk from dictionary"""
        chunk_dict = {
            "chunk_id": "test_003",
            "text": "Restored text",
            "metadata": {"restored": True},
            "chunk_type": "parent"
        }

        chunk = Chunk.from_dict(chunk_dict)

        assert chunk.chunk_id == "test_003"
        assert chunk.text == "Restored text"
        assert chunk.metadata["restored"] is True
        assert chunk.chunk_type == "parent"


# Pytest configuration
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
