from __future__ import annotations

import base64
import io
import json
import logging
import re
import tempfile
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import uuid

import requests
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from llama_index.core import Document, Settings, get_response_synthesizer, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama
from PIL import Image
from pptx import Presentation
import pytesseract
import fitz
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from backend.config import config
from utils import get_storage_context, search_web_results

# Try to import SerpAPI for Google Scholar
try:
    from serpapi import GoogleSearch
    SERPAPI_AVAILABLE = True
except ImportError:
    GoogleSearch = None
    SERPAPI_AVAILABLE = False

logger = logging.getLogger(__name__)


class ResearchService:
    def __init__(self) -> None:
        storage_context = get_storage_context()
        if storage_context is None:
            raise RuntimeError("Knowledge base is not initialized")
        self.index = load_index_from_storage(storage_context)
        self.chunker = SentenceSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )
        Settings.embed_model = HuggingFaceEmbedding(model_name=config.EMBEDDING_MODEL)
        # Use Ollama for LLM instead of OpenAI
        Settings.llm = Ollama(model="llama3.2:latest", request_timeout=120.0)
        self._ingest_lock = threading.Lock()
        self.upload_root = Path(config.USER_DATA_ROOT) / "knowledge_uploads"
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self._folder_cache: Optional[Dict[str, List[str]]] = None
        self._sanitize_pattern = re.compile(r"[^a-zA-Z0-9._-]")

    def _sanitize(self, value: str) -> str:
        safe = self._sanitize_pattern.sub("_", value)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"{timestamp}_{safe}"[:180]

    def _save_upload(self, filename: str, content: bytes) -> Path:
        safe_name = self._sanitize(filename)
        path = self.upload_root / safe_name
        with path.open("wb") as f:
            f.write(content)
        return path

    def _save_text_source(self, title: str, text: str, prefix: str) -> Path:
        safe_name = self._sanitize(f"{prefix}_{title}.txt")
        path = self.upload_root / safe_name
        path.write_text(text, encoding="utf-8")
        return path

    def _ingest_text(self, *, title: str, text: str, source: str, file_path: Optional[str]) -> None:
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("No text extracted from source")

        metadata = {
            "title": title,
            "source": source,
            "file_path": file_path or source,
            "last_modified": datetime.utcnow().isoformat(),
        }
        document = Document(text=clean_text, metadata=metadata)
        nodes = self.chunker.get_nodes_from_documents([document])
        with self._ingest_lock:
            self.index.insert_nodes(nodes)
            self.index.storage_context.persist(persist_dir=config.PERSIST_DIR)
            self._folder_cache = None

    def _extract_text_from_file(self, content: bytes, filename: str) -> Dict[str, object]:
        extension = Path(filename or "").suffix.lower()
        if extension in {".txt", ".md", ".csv"}:
            text = content.decode("utf-8", errors="ignore")
            preview_type = "text"
            thumbnail = None
        elif extension == ".pdf":
            with fitz.open(stream=content, filetype="pdf") as pdf_doc:
                texts = []
                for page in pdf_doc:
                    texts.append(page.get_text())
                text = "\n".join(texts)
            preview_type = "pdf"
            thumbnail = None
        elif extension == ".docx":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                doc = DocxDocument(tmp_path)
                text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            preview_type = "docx"
            thumbnail = None
        elif extension == ".pptx":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                presentation = Presentation(tmp_path)
                slides = []
                for slide in presentation.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text"):
                            slides.append(shape.text)
                text = "\n".join(slides)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
            preview_type = "pptx"
            thumbnail = None
        elif extension in {".png", ".jpg", ".jpeg"}:
            image = Image.open(io.BytesIO(content))
            try:
                text = pytesseract.image_to_string(image)
            except Exception:
                text = ""
            b64 = base64.b64encode(content).decode("utf-8")
            mime = f"image/{image.format.lower()}" if image.format else "image/png"
            thumbnail = f"data:{mime};base64,{b64}"
            preview_type = "image"
        else:
            raise ValueError(f"Unsupported file type: {extension}")

        excerpt = (text or "No readable text extracted.").strip()[:800]
        return {
            "text": text,
            "preview_type": preview_type,
            "thumbnail": thumbnail,
            "excerpt": excerpt or "No readable text extracted.",
        }

    def _structure(self) -> Dict[str, List[str]]:
        if self._folder_cache is not None:
            return self._folder_cache
        structure: Dict[str, List[str]] = {}
        for doc in self.index.docstore.docs.values():
            file_path = doc.metadata.get("file_path")
            if not file_path:
                continue
            folder = str(file_path.rsplit("/", 1)[0])
            structure.setdefault(folder, []).append(file_path)
        self._folder_cache = structure
        return structure

    def _normalize_label(self, label: str) -> str:
        return re.sub(r"[^a-z0-9]", "", label.lower())

    def list_folders(self) -> List[Dict[str, object]]:
        unique: Dict[str, Dict[str, object]] = {}
        for folder, files in self._structure().items():
            label = folder.split("/")[-1] or folder
            key = self._normalize_label(label)
            candidate = {
                "path": folder,
                "label": label,
                "file_count": len(files),
            }
            existing = unique.get(key)
            if existing is None or candidate["file_count"] > existing["file_count"]:
                unique[key] = candidate
        folders = list(unique.values())
        folders.sort(key=lambda item: str(item["label"]).lower())
        return folders

    def list_documents(self) -> List[Dict[str, object]]:
        docs = []
        for doc_id, doc in self.index.docstore.docs.items():
            metadata = doc.metadata or {}
            docs.append(
                {
                    "id": doc_id,
                    "title": metadata.get("title") or metadata.get("file_name") or "Untitled",
                    "file_path": metadata.get("file_path"),
                    "source": metadata.get("source"),
                    "last_modified": metadata.get("last_modified")
                    or metadata.get("timestamp")
                    or datetime.utcnow().isoformat(),
                }
            )
        docs.sort(key=lambda d: d["title"])
        return docs

    def list_uploads(self) -> List[Dict[str, object]]:
        uploads = []
        for path in sorted(self.upload_root.glob("*")):
            if not path.is_file():
                continue
            stat = path.stat()
            name = path.name
            parts = name.split("_", 1)
            original = parts[1] if len(parts) > 1 else name
            uploads.append(
                {
                    "id": name,
                    "file_name": original,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        uploads.sort(key=lambda item: item["uploaded_at"], reverse=True)
        return uploads

    def query(self, query: str, folders: Optional[List[str]] = None, uploaded_only: bool = False):
        structure = self._structure()
        filters = None

        # If uploaded_only is True, only search in knowledge_uploads folder
        if uploaded_only:
            # Find paths that contain 'knowledge_uploads' - handles both absolute and relative paths
            paths = []
            for folder, file_paths in structure.items():
                if "knowledge_uploads" in folder:
                    paths.extend(file_paths)
            if paths:
                filters = MetadataFilters(
                    filters=[ExactMatchFilter(key="file_path", value=path) for path in paths],
                    condition="or",
                )
            else:
                # No uploaded documents found
                return {
                    "answer": "No uploaded documents found. Please upload a document, URL, or YouTube video first.",
                    "sources": [],
                }
        elif folders:
            paths = []
            for folder in folders:
                paths.extend(structure.get(folder, []))
            if paths:
                filters = MetadataFilters(
                    filters=[ExactMatchFilter(key="file_path", value=path) for path in paths],
                    condition="or",
                )

        retriever = self.index.as_retriever(filters=filters, similarity_top_k=5)
        synthesizer = get_response_synthesizer(response_mode="compact")
        engine = RetrieverQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
        response = engine.query(query)

        sources = []
        for node in getattr(response, "source_nodes", []):
            metadata = node.metadata or {}
            sources.append(
                {
                    "score": node.score,
                    "excerpt": node.get_content()[:280],
                    "file_path": metadata.get("file_path"),
                    "title": metadata.get("title") or metadata.get("file_name"),
                }
            )

        return {
            "answer": str(response),
            "sources": sources,
        }

    def preview_file(self, content: bytes, filename: str) -> Dict[str, object]:
        stored_path = self._save_upload(filename, content)
        parsed = self._extract_text_from_file(content, filename)
        self._ingest_text(
            title=filename,
            text=parsed["text"],
            source="file_upload",
            file_path=str(stored_path),
        )
        return self._build_preview(
            parsed["preview_type"],
            filename,
            text=parsed["excerpt"],
            thumbnail=parsed["thumbnail"],
            source=str(stored_path),
        )

    def preview_url(self, url: str) -> Dict[str, object]:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SmartAITutor/1.0)",
        }
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ValueError(f"Unable to fetch URL: {exc}") from exc
        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        for element in soup(["script", "style", "nav", "footer", "aside"]):
            element.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if not text.strip():
            raise ValueError("No readable text extracted.")
        text_path = self._save_text_source(title or "web_page", text, "url")
        self._ingest_text(
            title=title,
            text=text,
            source=url,
            file_path=str(text_path),
        )
        return self._build_preview("webpage", title, text=text or "No readable text extracted.", source=url)

    def preview_youtube(self, url: str) -> Dict[str, object]:
        video_id = self._extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL")
        try:
            # Create API instance (new API requires instance)
            api = YouTubeTranscriptApi()
            segments = api.fetch(video_id)
        except (TranscriptsDisabled, NoTranscriptFound) as exc:
            raise ValueError("Transcript unavailable for this video") from exc
        except Exception as exc:
            raise ValueError(f"Failed to fetch transcript: {exc}") from exc

        # Extract text from segments (handle both dict and object formats)
        text_segments = []
        for segment in segments:
            if hasattr(segment, 'text'):
                text_segments.append(segment.text)
            elif isinstance(segment, dict):
                text_segments.append(segment.get("text", ""))

        transcript = " ".join(text_segments)
        title = f"YouTube Video: {video_id}"
        if not transcript.strip():
            raise ValueError("Transcript unavailable for this video")
        text_path = self._save_text_source(title, transcript, "youtube")
        self._ingest_text(
            title=title,
            text=transcript,
            source=url,
            file_path=str(text_path),
        )
        return self._build_preview("youtube", title, text=transcript, source=f"https://www.youtube.com/watch?v={video_id}")

    def _build_preview(
        self,
        preview_type: str,
        title: str,
        *,
        text: Optional[str] = None,
        thumbnail: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, object]:
        return {
            "preview_type": preview_type,
            "title": title,
            "excerpt": (text or "").strip()[:800],
            "thumbnail": thumbnail,
            "source": source,
        }

    def _extract_video_id(self, url: str) -> Optional[str]:
        # Simple and reliable patterns for YouTube URLs
        patterns = [
            r'[?&]v=([a-zA-Z0-9_-]{11})',  # watch?v=VIDEO_ID
            r'youtu\.be/([a-zA-Z0-9_-]{11})',  # youtu.be/VIDEO_ID
            r'/embed/([a-zA-Z0-9_-]{11})',  # /embed/VIDEO_ID
            r'/v/([a-zA-Z0-9_-]{11})',  # /v/VIDEO_ID
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        # Check if URL is just the video ID
        if re.fullmatch(r'[a-zA-Z0-9_-]{11}', url):
            return url
        return None

    # ==================== RESEARCH CAPABILITIES ====================

    def search_web(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search web for supplementary information."""
        try:
            results = search_web_results(query, max_results)
            return {
                "query": query,
                "web_results": results,
                "count": len(results),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return {
                "query": query,
                "web_results": [],
                "count": 0,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def search_academic_papers(
        self, query: str, sources: Optional[List[str]] = None, max_results: int = 10
    ) -> Dict[str, Any]:
        """Search academic databases for relevant papers."""
        sources = sources or ["arxiv", "pubmed", "scholar"]
        papers = []
        errors = []

        for source in sources:
            try:
                if source == "arxiv":
                    papers.extend(self._search_arxiv(query, max_results // len(sources) + 1))
                elif source == "pubmed":
                    papers.extend(self._search_pubmed(query, max_results // len(sources) + 1))
                elif source == "scholar" and SERPAPI_AVAILABLE:
                    papers.extend(self._search_google_scholar(query, max_results // len(sources) + 1))
            except Exception as e:
                logger.error(f"Academic search failed for {source}: {e}")
                errors.append({"source": source, "error": str(e)})

        return {
            "query": query,
            "papers": papers[:max_results],
            "sources_searched": sources,
            "count": len(papers[:max_results]),
            "errors": errors if errors else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _search_arxiv(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search arXiv API for papers."""
        encoded_query = urllib.parse.quote(query)
        url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&max_results={max_results}&sortBy=relevance"

        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            ns = {"atom": "http://www.w3.org/2005/Atom"}
            papers = []

            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns)
                summary = entry.find("atom:summary", ns)
                published = entry.find("atom:published", ns)
                link = entry.find("atom:id", ns)
                authors = entry.findall("atom:author/atom:name", ns)

                papers.append({
                    "title": title.text.strip().replace("\n", " ") if title is not None else "Unknown",
                    "abstract": summary.text.strip()[:500] if summary is not None else "",
                    "authors": [a.text for a in authors][:5],
                    "url": link.text if link is not None else "",
                    "source": "arxiv",
                    "published_date": published.text[:10] if published is not None else None,
                })

            return papers
        except Exception as e:
            logger.error(f"arXiv search error: {e}")
            return []

    def _search_pubmed(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search PubMed/NCBI for papers using E-utilities."""
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

        try:
            # First, search for IDs
            search_url = f"{base_url}/esearch.fcgi?db=pubmed&term={urllib.parse.quote(query)}&retmax={max_results}&retmode=json"
            search_response = requests.get(search_url, timeout=15)
            search_data = search_response.json()
            ids = search_data.get("esearchresult", {}).get("idlist", [])

            if not ids:
                return []

            # Fetch details for each ID
            fetch_url = f"{base_url}/esummary.fcgi?db=pubmed&id={','.join(ids)}&retmode=json"
            fetch_response = requests.get(fetch_url, timeout=15)
            fetch_data = fetch_response.json()

            papers = []
            results = fetch_data.get("result", {})
            for pmid in ids:
                if pmid not in results:
                    continue
                article = results[pmid]
                authors = article.get("authors", [])
                papers.append({
                    "title": article.get("title", "Unknown"),
                    "abstract": article.get("sorttitle", "")[:500],
                    "authors": [a.get("name", "") for a in authors[:5]],
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "source": "pubmed",
                    "published_date": article.get("pubdate", None),
                    "doi": article.get("elocationid", None),
                })

            return papers
        except Exception as e:
            logger.error(f"PubMed search error: {e}")
            return []

    def _search_google_scholar(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search Google Scholar via SerpAPI."""
        if not SERPAPI_AVAILABLE or GoogleSearch is None:
            return []

        serpapi_key = getattr(config, "SERPAPI_API_KEY", None) or ""
        if not serpapi_key:
            return []

        try:
            search = GoogleSearch({
                "q": query,
                "engine": "google_scholar",
                "api_key": serpapi_key,
                "num": max_results,
            })
            results = search.get_dict()
            papers = []

            for result in results.get("organic_results", [])[:max_results]:
                papers.append({
                    "title": result.get("title", "Unknown"),
                    "abstract": result.get("snippet", "")[:500],
                    "authors": [a.get("name", "") for a in result.get("publication_info", {}).get("authors", [])][:5],
                    "url": result.get("link", ""),
                    "source": "scholar",
                    "published_date": result.get("publication_info", {}).get("summary", ""),
                    "cited_by": result.get("inline_links", {}).get("cited_by", {}).get("total", 0),
                })

            return papers
        except Exception as e:
            logger.error(f"Google Scholar search error: {e}")
            return []

    def compare_sources(
        self, topic: str, document_ids: Optional[List[str]] = None, uploaded_only: bool = True
    ) -> Dict[str, Any]:
        """Compare information across multiple documents on a given topic."""
        # Get relevant content from each document
        comparisons = []

        if uploaded_only:
            # Get all uploaded documents
            structure = self._structure()
            paths = []
            for folder, file_paths in structure.items():
                if "knowledge_uploads" in folder:
                    paths.extend(file_paths)

            # Query each document separately
            for path in paths[:5]:  # Limit to 5 documents
                filters = MetadataFilters(
                    filters=[ExactMatchFilter(key="file_path", value=path)],
                    condition="or",
                )
                retriever = self.index.as_retriever(filters=filters, similarity_top_k=3)
                nodes = retriever.retrieve(topic)

                if nodes:
                    doc_title = nodes[0].metadata.get("title", path.split("/")[-1])
                    excerpts = [node.get_content()[:300] for node in nodes]
                    comparisons.append({
                        "document_title": doc_title,
                        "file_path": path,
                        "excerpts": excerpts,
                        "relevance_score": sum(n.score or 0 for n in nodes) / len(nodes),
                    })

        # Use LLM to analyze comparisons
        if comparisons:
            analysis = self._analyze_comparisons(topic, comparisons)
        else:
            analysis = {
                "agreements": [],
                "contradictions": [],
                "summary": "No documents found to compare.",
            }

        return {
            "topic": topic,
            "documents_analyzed": len(comparisons),
            "comparisons": comparisons,
            "agreements": analysis.get("agreements", []),
            "contradictions": analysis.get("contradictions", []),
            "summary": analysis.get("summary", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _analyze_comparisons(self, topic: str, comparisons: List[Dict]) -> Dict[str, Any]:
        """Use LLM to analyze comparisons between documents."""
        if not comparisons:
            return {"agreements": [], "contradictions": [], "summary": "No content to analyze."}

        # Build context from comparisons
        context_parts = []
        for i, comp in enumerate(comparisons, 1):
            context_parts.append(f"Document {i}: {comp['document_title']}")
            for excerpt in comp.get("excerpts", []):
                context_parts.append(f"  - {excerpt}")

        context = "\n".join(context_parts)

        prompt = f"""Analyze the following document excerpts about "{topic}" and identify:
1. Key agreements (points where documents say similar things)
2. Contradictions (points where documents disagree)
3. A brief summary of the overall findings

Documents:
{context}

Respond in JSON format:
{{"agreements": ["agreement 1", "agreement 2"], "contradictions": ["contradiction 1"], "summary": "brief summary"}}
"""

        try:
            synthesizer = get_response_synthesizer(response_mode="compact")
            # Simple query to get analysis
            retriever = self.index.as_retriever(similarity_top_k=1)
            engine = RetrieverQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
            response = engine.query(prompt)

            # Try to parse JSON from response
            response_text = str(response)
            # Extract JSON if embedded in response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {
                "agreements": [],
                "contradictions": [],
                "summary": response_text[:500],
            }
        except Exception as e:
            logger.error(f"Comparison analysis error: {e}")
            return {
                "agreements": [],
                "contradictions": [],
                "summary": f"Analysis could not be completed: {str(e)}",
            }

    def extract_citations(
        self, document_id: Optional[str] = None, format_style: str = "apa"
    ) -> Dict[str, Any]:
        """Extract and format citations from documents."""
        # Get content from uploaded documents
        content = self._get_uploaded_content()

        if not content:
            return {
                "citations": [],
                "format": format_style,
                "count": 0,
                "exportable_bibliography": "",
                "message": "No documents found to extract citations from.",
            }

        # Detect citations using patterns
        citations = self._detect_citations(content)

        # Format citations
        formatted_citations = []
        for citation in citations:
            formatted = self._format_citation(citation, format_style)
            formatted_citations.append({
                "raw": citation.get("raw", ""),
                "formatted": formatted,
                "authors": citation.get("authors", []),
                "title": citation.get("title", ""),
                "year": citation.get("year", ""),
            })

        # Generate bibliography
        bibliography = "\n\n".join([c["formatted"] for c in formatted_citations])

        return {
            "citations": formatted_citations,
            "format": format_style,
            "count": len(formatted_citations),
            "exportable_bibliography": bibliography,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _get_uploaded_content(self) -> str:
        """Get all content from uploaded documents."""
        structure = self._structure()
        content_parts = []

        for folder, paths in structure.items():
            if "knowledge_uploads" in folder:
                for path in paths:
                    for doc in self.index.docstore.docs.values():
                        if doc.metadata.get("file_path") == path:
                            content_parts.append(doc.get_content())

        return "\n\n".join(content_parts)

    def _detect_citations(self, content: str) -> List[Dict[str, Any]]:
        """Detect citations in text using regex patterns."""
        citations = []

        # Common citation patterns
        patterns = [
            # APA style: Author (Year)
            r'([A-Z][a-z]+(?:,?\s+(?:&\s+)?[A-Z][a-z]+)*)\s*\((\d{4})\)',
            # Numbered references: [1], [2,3]
            r'\[(\d+(?:,\s*\d+)*)\]',
            # Full reference line
            r'([A-Z][a-z]+,\s*[A-Z]\.(?:\s*[A-Z]\.)*(?:,?\s*(?:&\s*)?[A-Z][a-z]+,\s*[A-Z]\.(?:\s*[A-Z]\.)*)*\s*\(\d{4}\)[^.]*\.)',
        ]

        seen = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                raw = match if isinstance(match, str) else " ".join(match)
                if raw not in seen and len(raw) > 5:
                    seen.add(raw)
                    # Try to extract components
                    year_match = re.search(r'\((\d{4})\)', raw)
                    citations.append({
                        "raw": raw,
                        "year": year_match.group(1) if year_match else "",
                        "authors": self._extract_authors(raw),
                        "title": "",
                    })

        return citations[:50]  # Limit to 50 citations

    def _extract_authors(self, text: str) -> List[str]:
        """Extract author names from citation text."""
        # Remove year
        text = re.sub(r'\(\d{4}\)', '', text)
        # Split by common separators
        parts = re.split(r',\s*&\s*|,\s+and\s+|,\s*', text)
        authors = [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]
        return authors[:5]

    def _format_citation(self, citation: Dict[str, Any], style: str) -> str:
        """Format a citation in the specified style."""
        authors = citation.get("authors", [])
        year = citation.get("year", "n.d.")
        title = citation.get("title", "")
        raw = citation.get("raw", "")

        if not authors:
            return raw

        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        if style == "apa":
            return f"{author_str} ({year}). {title}." if title else f"{author_str} ({year})."
        elif style == "mla":
            return f"{author_str}. {title}. {year}." if title else f"{author_str}. {year}."
        elif style == "chicago":
            return f"{author_str}. {year}. {title}." if title else f"{author_str}. {year}."
        elif style == "ieee":
            return f"{author_str}, \"{title},\" {year}." if title else f"{author_str}, {year}."
        else:
            return raw

    def generate_summary(
        self, document_id: Optional[str] = None, mode: str = "executive", max_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate document summary in specified mode."""
        content = self._get_uploaded_content()

        if not content:
            return {
                "mode": mode,
                "summary": "No documents found to summarize.",
                "source_document": document_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        # Truncate content if too long
        content = content[:10000]

        prompts = {
            "executive": f"Provide a brief executive summary of the following document in 3-5 sentences, focusing on the key points and main conclusions:\n\n{content}",
            "detailed": f"Provide a comprehensive detailed analysis of the following document, covering all major topics, methodologies, findings, and conclusions:\n\n{content}",
            "bullets": f"Summarize the following document as a bulleted list of 10-15 key takeaways:\n\n{content}",
        }

        if mode == "custom" and max_length:
            prompt = f"Summarize the following document in approximately {max_length} words:\n\n{content}"
        else:
            prompt = prompts.get(mode, prompts["executive"])

        try:
            synthesizer = get_response_synthesizer(response_mode="compact")
            retriever = self.index.as_retriever(similarity_top_k=1)
            engine = RetrieverQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
            response = engine.query(prompt)

            return {
                "mode": mode,
                "summary": str(response),
                "source_document": document_id,
                "word_count": len(str(response).split()),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            return {
                "mode": mode,
                "summary": f"Summary generation failed: {str(e)}",
                "source_document": document_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def generate_questions(
        self,
        document_id: Optional[str] = None,
        difficulty: str = "medium",
        question_types: Optional[List[str]] = None,
        count: int = 5,
    ) -> Dict[str, Any]:
        """Generate study questions from documents."""
        question_types = question_types or ["mcq", "short_answer"]
        content = self._get_uploaded_content()

        if not content:
            return {
                "questions": [],
                "difficulty": difficulty,
                "types": question_types,
                "source_document": document_id,
                "message": "No documents found to generate questions from.",
                "timestamp": datetime.utcnow().isoformat(),
            }

        content = content[:8000]  # Limit content length

        type_instructions = {
            "mcq": "multiple choice questions with 4 options (A, B, C, D) and indicate the correct answer",
            "short_answer": "short answer questions that can be answered in 1-2 sentences",
            "essay": "essay prompts that require detailed analysis and critical thinking",
        }

        type_desc = " and ".join([type_instructions.get(t, t) for t in question_types])

        difficulty_guide = {
            "easy": "basic recall and understanding",
            "medium": "application and analysis",
            "hard": "synthesis, evaluation, and critical thinking",
        }

        prompt = f"""Based on the following content, generate {count} {type_desc}.

Difficulty level: {difficulty} ({difficulty_guide.get(difficulty, 'medium level')})

Content:
{content}

Format each question as JSON:
{{"id": "q1", "question": "...", "type": "mcq|short_answer|essay", "difficulty": "{difficulty}", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "answer": "correct answer or key points", "explanation": "why this is the answer"}}

Return a JSON array of questions."""

        try:
            synthesizer = get_response_synthesizer(response_mode="compact")
            retriever = self.index.as_retriever(similarity_top_k=1)
            engine = RetrieverQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
            response = engine.query(prompt)

            # Parse questions from response
            response_text = str(response)
            questions = self._parse_questions(response_text, question_types, difficulty, count)

            return {
                "questions": questions,
                "difficulty": difficulty,
                "types": question_types,
                "count": len(questions),
                "source_document": document_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Question generation error: {e}")
            return {
                "questions": [],
                "difficulty": difficulty,
                "types": question_types,
                "source_document": document_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def _parse_questions(
        self, response: str, question_types: List[str], difficulty: str, count: int
    ) -> List[Dict[str, Any]]:
        """Parse questions from LLM response."""
        questions = []

        # Try to parse JSON array
        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, list):
                    return parsed[:count]
        except json.JSONDecodeError:
            pass

        # Fallback: extract questions manually
        lines = response.split('\n')
        current_q = None

        for line in lines:
            line = line.strip()
            if re.match(r'^(\d+\.|Q\d+|Question)', line, re.IGNORECASE):
                if current_q:
                    questions.append(current_q)
                current_q = {
                    "id": f"q{len(questions) + 1}",
                    "question": re.sub(r'^(\d+\.|Q\d+:|Question\s*\d*:?)\s*', '', line),
                    "type": question_types[0] if question_types else "short_answer",
                    "difficulty": difficulty,
                    "options": [],
                    "answer": "",
                    "explanation": "",
                }
            elif current_q and re.match(r'^[A-D][.\)]\s*', line):
                current_q["options"].append(line)
                current_q["type"] = "mcq"
            elif current_q and line.lower().startswith(("answer:", "correct:")):
                current_q["answer"] = re.sub(r'^(answer:|correct:)\s*', '', line, flags=re.IGNORECASE)

        if current_q:
            questions.append(current_q)

        return questions[:count]

    def fact_check(
        self, claim: str, uploaded_only: bool = True, include_web: bool = False
    ) -> Dict[str, Any]:
        """Cross-reference claims across sources."""
        evidence_sources = []

        # Search uploaded documents
        doc_response = self.query(claim, uploaded_only=uploaded_only)

        for source in doc_response.get("sources", []):
            support_analysis = self._evaluate_support(claim, source.get("excerpt", ""))
            evidence_sources.append({
                "source_type": "document",
                "title": source.get("title", "Unknown"),
                "excerpt": source.get("excerpt", ""),
                "supports_claim": support_analysis["supports"],
                "confidence": source.get("score", 0),
                "analysis": support_analysis["reason"],
            })

        # Optionally search web
        if include_web:
            web_results = self.search_web(claim)
            for result in web_results.get("web_results", [])[:3]:
                support_analysis = self._evaluate_support(claim, result.get("content", ""))
                evidence_sources.append({
                    "source_type": "web",
                    "title": result.get("title", "Unknown"),
                    "url": result.get("url", ""),
                    "excerpt": result.get("content", "")[:300],
                    "supports_claim": support_analysis["supports"],
                    "confidence": 0.5,  # Default confidence for web sources
                    "analysis": support_analysis["reason"],
                })

        # Calculate verdict
        verdict = self._calculate_verdict(evidence_sources)

        return {
            "claim": claim,
            "verdict": verdict["verdict"],
            "confidence": verdict["confidence"],
            "supporting_sources": [s for s in evidence_sources if s["supports_claim"]],
            "contradicting_sources": [s for s in evidence_sources if not s["supports_claim"]],
            "evidence": evidence_sources,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _evaluate_support(self, claim: str, evidence: str) -> Dict[str, Any]:
        """Evaluate if evidence supports a claim."""
        if not evidence:
            return {"supports": False, "reason": "No evidence provided"}

        # Simple keyword matching as fallback
        claim_words = set(claim.lower().split())
        evidence_words = set(evidence.lower().split())
        overlap = len(claim_words & evidence_words) / max(len(claim_words), 1)

        # Use LLM for better analysis
        try:
            prompt = f"""Does the following evidence support, contradict, or is neutral to the claim?

Claim: {claim}

Evidence: {evidence[:500]}

Respond with: SUPPORTS, CONTRADICTS, or NEUTRAL followed by a brief reason."""

            synthesizer = get_response_synthesizer(response_mode="compact")
            retriever = self.index.as_retriever(similarity_top_k=1)
            engine = RetrieverQueryEngine(retriever=retriever, response_synthesizer=synthesizer)
            response = str(engine.query(prompt)).upper()

            if "SUPPORTS" in response:
                return {"supports": True, "reason": "Evidence supports the claim"}
            elif "CONTRADICTS" in response:
                return {"supports": False, "reason": "Evidence contradicts the claim"}
            else:
                return {"supports": overlap > 0.3, "reason": "Evidence is neutral or unclear"}
        except Exception:
            return {"supports": overlap > 0.3, "reason": f"Keyword overlap: {overlap:.0%}"}

    def _calculate_verdict(self, evidence_sources: List[Dict]) -> Dict[str, Any]:
        """Calculate overall verdict from evidence sources."""
        if not evidence_sources:
            return {"verdict": "inconclusive", "confidence": 0.0}

        supporting = sum(1 for s in evidence_sources if s.get("supports_claim"))
        contradicting = len(evidence_sources) - supporting
        total = len(evidence_sources)

        support_ratio = supporting / total if total > 0 else 0
        avg_confidence = sum(s.get("confidence", 0) for s in evidence_sources) / total if total > 0 else 0

        if support_ratio >= 0.7:
            verdict = "supported"
            confidence = min(support_ratio * avg_confidence * 1.2, 1.0)
        elif support_ratio <= 0.3:
            verdict = "contradicted"
            confidence = min((1 - support_ratio) * avg_confidence * 1.2, 1.0)
        else:
            verdict = "inconclusive"
            confidence = 0.5

        return {"verdict": verdict, "confidence": round(confidence, 2)}

    # ==================== END RESEARCH CAPABILITIES ====================

    def clear_uploads(self) -> Dict[str, int]:
        """Clear all uploaded documents from knowledge_uploads folder and remove from index."""
        deleted_files = 0
        deleted_docs = 0

        # Delete files from knowledge_uploads folder
        with self._ingest_lock:
            for file_path in self.upload_root.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    deleted_files += 1

            # Remove documents from index that are in knowledge_uploads
            docs_to_remove = []
            for doc_id, doc in list(self.index.docstore.docs.items()):
                metadata = doc.metadata or {}
                file_path = metadata.get("file_path", "")
                if "knowledge_uploads" in file_path:
                    docs_to_remove.append(doc_id)

            for doc_id in docs_to_remove:
                try:
                    self.index.docstore.delete_document(doc_id)
                    deleted_docs += 1
                except Exception:
                    pass

            # Persist the updated index
            if deleted_docs > 0:
                self.index.storage_context.persist(persist_dir=config.PERSIST_DIR)
                self._folder_cache = None

        return {"deleted_files": deleted_files, "deleted_docs": deleted_docs, "deleted_count": deleted_files}


_research_service: Optional[ResearchService] = None


def get_research_service() -> ResearchService:
    global _research_service
    if _research_service is None:
        _research_service = ResearchService()
    return _research_service
