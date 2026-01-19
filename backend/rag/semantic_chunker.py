"""
Advanced Semantic Chunking Module

Implements state-of-the-art chunking strategies:
1. Semantic Chunking - Split by meaning, not fixed size
2. Structure-Aware Chunking - Preserve document structure
3. Contextual Enrichment - Add metadata to chunks
4. Parent-Child Chunking - Hierarchical relationships

Author: Smart AI Tutor Team
Date: December 28, 2025
"""

import re
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

import nltk
from nltk.tokenize import sent_tokenize
import spacy

from backend.config import config
from backend.logger import get_logger

logger = get_logger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# Load spaCy model for advanced NLP
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    logger.warning("spaCy model not found. Run: python -m spacy download en_core_web_sm")
    nlp = None


class ChunkType(Enum):
    """Types of chunks based on document structure"""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    CODE = "code"
    QUOTE = "quote"
    MIXED = "mixed"


@dataclass
class Chunk:
    """Represents a semantic chunk with metadata"""
    text: str
    chunk_id: str
    chunk_type: ChunkType = ChunkType.PARAGRAPH
    start_char: int = 0
    end_char: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Generate chunk ID if not provided"""
        if not self.chunk_id:
            self.chunk_id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique chunk ID based on content and position"""
        content_hash = hashlib.md5(self.text.encode()).hexdigest()[:8]
        return f"chunk_{self.start_char}_{content_hash}"

    def enrich_context(self, doc_title: str = "", section_header: str = "", page_num: Optional[int] = None):
        """Add contextual metadata to chunk"""
        if doc_title:
            self.metadata['document_title'] = doc_title
        if section_header:
            self.metadata['section_header'] = section_header
        if page_num is not None:
            self.metadata['page_number'] = page_num

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'chunk_id': self.chunk_id,
            'text': self.text,
            'chunk_type': self.chunk_type.value,
            'start_char': self.start_char,
            'end_char': self.end_char,
            'metadata': self.metadata,
            'parent_chunk_id': self.parent_chunk_id,
            'child_chunk_ids': self.child_chunk_ids
        }


class SemanticChunker:
    """
    Advanced semantic chunking with structure awareness

    Features:
    - Sentence-level splitting (not fixed character count)
    - Document structure preservation (headings, tables, code)
    - Contextual enrichment (title, section headers)
    - Parent-child relationships
    - Adaptive chunk sizing
    """

    def __init__(
        self,
        target_chunk_size: int = 512,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1024,
        overlap_sentences: int = 1,
        preserve_structure: bool = True,
        enrich_context: bool = True,
        enable_parent_child: bool = False,
        parent_chunk_size: int = 2048
    ):
        """
        Initialize semantic chunker

        Args:
            target_chunk_size: Target characters per chunk (flexible)
            min_chunk_size: Minimum chunk size to avoid tiny chunks
            max_chunk_size: Maximum chunk size before forced split
            overlap_sentences: Number of sentences to overlap
            preserve_structure: Keep document structure (headings, tables)
            enrich_context: Add metadata (title, section headers)
            enable_parent_child: Create parent-child chunk relationships
            parent_chunk_size: Size of parent chunks
        """
        self.target_chunk_size = target_chunk_size
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap_sentences = overlap_sentences
        self.preserve_structure = preserve_structure
        self.enrich_context = enrich_context
        self.enable_parent_child = enable_parent_child
        self.parent_chunk_size = parent_chunk_size

        logger.info(
            f"SemanticChunker initialized: target={target_chunk_size}, "
            f"structure={preserve_structure}, enrich={enrich_context}"
        )

    def chunk_text(
        self,
        text: str,
        doc_title: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk text using semantic boundaries

        Args:
            text: Input text to chunk
            doc_title: Document title for context enrichment
            metadata: Additional metadata to attach to chunks

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to chunker")
            return []

        metadata = metadata or {}

        # Step 1: Detect and preserve structure
        if self.preserve_structure:
            structured_blocks = self._detect_structure(text)
        else:
            structured_blocks = [{'type': ChunkType.PARAGRAPH, 'text': text}]

        # Step 2: Chunk each block semantically
        all_chunks = []
        current_section = ""

        for block in structured_blocks:
            block_type = block['type']
            block_text = block['text']

            # Update section header for context
            if block_type == ChunkType.HEADING:
                current_section = block_text.strip()

            # Chunk the block
            if block_type == ChunkType.CODE or block_type == ChunkType.TABLE:
                # Don't split code or tables
                chunks = [self._create_chunk(block_text, block_type, all_chunks)]
            else:
                # Semantic splitting for text
                chunks = self._semantic_split(block_text, block_type, all_chunks)

            # Enrich with context
            if self.enrich_context:
                for chunk in chunks:
                    chunk.enrich_context(
                        doc_title=doc_title,
                        section_header=current_section
                    )
                    chunk.metadata.update(metadata)

            all_chunks.extend(chunks)

        # Step 3: Create parent-child relationships if enabled
        if self.enable_parent_child:
            all_chunks = self._create_parent_child_relationships(all_chunks)

        logger.info(f"Created {len(all_chunks)} chunks from document '{doc_title}'")
        return all_chunks

    def _detect_structure(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect document structure (headings, tables, code blocks, lists)

        Returns:
            List of structured blocks with type and text
        """
        blocks = []

        # Patterns for different structures
        heading_pattern = r'^(#{1,6}\s+.+|[A-Z][A-Za-z\s]+\n[=\-]{3,})$'
        code_block_pattern = r'```[\s\S]*?```|`[^`]+`'
        table_pattern = r'\|[^\n]+\|[\s\S]*?\|[^\n]+\|'
        list_pattern = r'^(\s*[-*+]\s+.+|^\s*\d+\.\s+.+)$'
        quote_pattern = r'^>\s+.+'

        # Split text into lines for structure detection
        lines = text.split('\n')
        current_block = []
        current_type = ChunkType.PARAGRAPH

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for code block
            if '```' in line:
                if current_block:
                    blocks.append({'type': current_type, 'text': '\n'.join(current_block)})
                    current_block = []

                # Extract full code block
                code_lines = [line]
                i += 1
                while i < len(lines) and '```' not in lines[i]:
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines):
                    code_lines.append(lines[i])

                blocks.append({'type': ChunkType.CODE, 'text': '\n'.join(code_lines)})
                current_type = ChunkType.PARAGRAPH
                i += 1
                continue

            # Check for heading
            elif re.match(heading_pattern, line, re.MULTILINE):
                if current_block:
                    blocks.append({'type': current_type, 'text': '\n'.join(current_block)})
                    current_block = []

                blocks.append({'type': ChunkType.HEADING, 'text': line})
                current_type = ChunkType.PARAGRAPH
                i += 1
                continue

            # Check for table
            elif re.match(table_pattern, line):
                if current_block:
                    blocks.append({'type': current_type, 'text': '\n'.join(current_block)})
                    current_block = []

                # Extract full table
                table_lines = [line]
                i += 1
                while i < len(lines) and '|' in lines[i]:
                    table_lines.append(lines[i])
                    i += 1

                blocks.append({'type': ChunkType.TABLE, 'text': '\n'.join(table_lines)})
                current_type = ChunkType.PARAGRAPH
                continue

            # Check for list
            elif re.match(list_pattern, line, re.MULTILINE):
                if current_type != ChunkType.LIST and current_block:
                    blocks.append({'type': current_type, 'text': '\n'.join(current_block)})
                    current_block = []

                current_type = ChunkType.LIST
                current_block.append(line)
                i += 1
                continue

            # Check for quote
            elif re.match(quote_pattern, line):
                if current_type != ChunkType.QUOTE and current_block:
                    blocks.append({'type': current_type, 'text': '\n'.join(current_block)})
                    current_block = []

                current_type = ChunkType.QUOTE
                current_block.append(line)
                i += 1
                continue

            # Regular paragraph
            else:
                if current_type not in [ChunkType.PARAGRAPH, ChunkType.LIST, ChunkType.QUOTE] and current_block:
                    blocks.append({'type': current_type, 'text': '\n'.join(current_block)})
                    current_block = []
                    current_type = ChunkType.PARAGRAPH

                if line.strip():  # Non-empty line
                    current_block.append(line)
                else:  # Empty line = paragraph break
                    if current_block:
                        blocks.append({'type': current_type, 'text': '\n'.join(current_block)})
                        current_block = []
                        current_type = ChunkType.PARAGRAPH

                i += 1

        # Add remaining block
        if current_block:
            blocks.append({'type': current_type, 'text': '\n'.join(current_block)})

        return blocks

    def _semantic_split(
        self,
        text: str,
        chunk_type: ChunkType,
        existing_chunks: List[Chunk]
    ) -> List[Chunk]:
        """
        Split text at semantic boundaries (sentences, not characters)

        Args:
            text: Text to split
            chunk_type: Type of chunk
            existing_chunks: Previously created chunks (for overlap)

        Returns:
            List of chunks
        """
        # Tokenize into sentences
        try:
            sentences = sent_tokenize(text)
        except Exception as e:
            logger.warning(f"Sentence tokenization failed: {e}. Using simple split.")
            sentences = re.split(r'[.!?]+\s+', text)

        chunks = []
        current_chunk_sentences = []
        current_length = 0
        overlap_buffer = []

        for sentence in sentences:
            sentence_length = len(sentence)

            # Check if adding this sentence exceeds max size
            if current_length + sentence_length > self.max_chunk_size and current_chunk_sentences:
                # Create chunk from accumulated sentences
                chunk_text = ' '.join(current_chunk_sentences)
                chunk = self._create_chunk(chunk_text, chunk_type, existing_chunks + chunks)
                chunks.append(chunk)

                # Prepare overlap for next chunk
                if self.overlap_sentences > 0:
                    overlap_buffer = current_chunk_sentences[-self.overlap_sentences:]
                else:
                    overlap_buffer = []

                # Start new chunk with overlap
                current_chunk_sentences = overlap_buffer + [sentence]
                current_length = sum(len(s) for s in current_chunk_sentences)
            else:
                # Add sentence to current chunk
                current_chunk_sentences.append(sentence)
                current_length += sentence_length

                # Check if we've reached target size (but still allow more sentences)
                if current_length >= self.target_chunk_size:
                    # Only split if next sentence would exceed max_chunk_size
                    # This creates natural boundaries
                    pass

        # Add final chunk if it meets minimum size
        if current_chunk_sentences:
            chunk_text = ' '.join(current_chunk_sentences)
            if len(chunk_text) >= self.min_chunk_size or not chunks:
                chunk = self._create_chunk(chunk_text, chunk_type, existing_chunks + chunks)
                chunks.append(chunk)
            elif chunks:
                # Merge with previous chunk if too small
                chunks[-1].text += ' ' + chunk_text
                chunks[-1].end_char += len(chunk_text) + 1

        return chunks

    def _create_chunk(
        self,
        text: str,
        chunk_type: ChunkType,
        existing_chunks: List[Chunk]
    ) -> Chunk:
        """Create a Chunk object with proper positioning"""
        # Calculate start position based on existing chunks
        if existing_chunks:
            start_char = existing_chunks[-1].end_char + 1
        else:
            start_char = 0

        end_char = start_char + len(text)

        chunk = Chunk(
            text=text,
            chunk_id="",  # Will be auto-generated
            chunk_type=chunk_type,
            start_char=start_char,
            end_char=end_char
        )

        return chunk

    def _create_parent_child_relationships(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Create parent-child chunk relationships for better context

        Child chunks are original chunks.
        Parent chunks are larger aggregations of children.

        Args:
            chunks: List of child chunks

        Returns:
            List containing both parent and child chunks
        """
        if not chunks:
            return []

        parent_chunks = []
        all_chunks = []

        i = 0
        while i < len(chunks):
            # Aggregate chunks into parent
            parent_text_parts = []
            child_ids = []
            parent_start = chunks[i].start_char
            parent_end = parent_start

            # Collect chunks until we reach parent size
            while i < len(chunks) and len(' '.join(parent_text_parts)) < self.parent_chunk_size:
                child = chunks[i]
                parent_text_parts.append(child.text)
                child_ids.append(child.chunk_id)
                parent_end = child.end_char
                i += 1

            # Create parent chunk
            parent_text = ' '.join(parent_text_parts)
            parent_chunk = Chunk(
                text=parent_text,
                chunk_id=f"parent_{parent_start}",
                chunk_type=ChunkType.MIXED,
                start_char=parent_start,
                end_char=parent_end,
                metadata={'is_parent': True, 'child_count': len(child_ids)},
                child_chunk_ids=child_ids
            )

            # Update children to reference parent
            for child_id in child_ids:
                child_chunk = next((c for c in chunks if c.chunk_id == child_id), None)
                if child_chunk:
                    child_chunk.parent_chunk_id = parent_chunk.chunk_id

            parent_chunks.append(parent_chunk)

        # Return parents first, then children
        all_chunks = parent_chunks + chunks

        logger.info(f"Created {len(parent_chunks)} parent chunks from {len(chunks)} child chunks")
        return all_chunks

    def chunk_file(
        self,
        file_path: str,
        doc_title: Optional[str] = None
    ) -> List[Chunk]:
        """
        Chunk a file with automatic title extraction

        Args:
            file_path: Path to file
            doc_title: Optional document title (auto-detected if not provided)

        Returns:
            List of chunks
        """
        import os
        from pathlib import Path

        path = Path(file_path)

        # Auto-detect title from filename if not provided
        if not doc_title:
            doc_title = path.stem

        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return []

        # Add file metadata
        metadata = {
            'file_name': path.name,
            'file_path': str(path.absolute()),
            'file_size': path.stat().st_size,
            'file_extension': path.suffix
        }

        return self.chunk_text(text, doc_title=doc_title, metadata=metadata)


# Factory function
def create_semantic_chunker(
    target_size: int = None,
    preserve_structure: bool = True,
    enrich_context: bool = True,
    enable_parent_child: bool = False
) -> SemanticChunker:
    """
    Create a semantic chunker with config defaults

    Args:
        target_size: Target chunk size (defaults to config.CHUNK_SIZE)
        preserve_structure: Preserve document structure
        enrich_context: Add contextual metadata
        enable_parent_child: Enable parent-child chunking

    Returns:
        SemanticChunker instance
    """
    return SemanticChunker(
        target_chunk_size=target_size or config.CHUNK_SIZE,
        preserve_structure=preserve_structure,
        enrich_context=enrich_context,
        enable_parent_child=enable_parent_child,
        parent_chunk_size=config.PARENT_CHUNK_SIZE
    )


# Example usage
if __name__ == "__main__":
    # Test the chunker
    sample_text = """
    # Introduction to Machine Learning

    Machine learning is a subset of artificial intelligence. It focuses on building systems that learn from data.

    ## Types of Machine Learning

    1. Supervised Learning
    2. Unsupervised Learning
    3. Reinforcement Learning

    ### Supervised Learning

    Supervised learning uses labeled data to train models. The model learns to map inputs to outputs.

    Example code:
    ```python
    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(X_train, y_train)
    ```

    This is a powerful technique used in many applications.
    """

    chunker = create_semantic_chunker(target_size=200, preserve_structure=True, enrich_context=True)
    chunks = chunker.chunk_text(sample_text, doc_title="ML Introduction")

    print(f"\nCreated {len(chunks)} chunks:\n")
    for i, chunk in enumerate(chunks, 1):
        print(f"Chunk {i} ({chunk.chunk_type.value}):")
        print(f"  Text: {chunk.text[:80]}...")
        print(f"  Metadata: {chunk.metadata}")
        print()
