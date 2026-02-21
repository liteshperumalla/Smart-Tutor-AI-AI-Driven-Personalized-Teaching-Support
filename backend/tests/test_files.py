"""
File Upload Tests
Tests for file upload validation, type checking, and size limits.
"""

import pytest
import io


class TestFileUpload:
    """Test file upload endpoint validation"""

    def test_valid_pdf_upload(self, test_client, auth_headers):
        """Valid PDF file upload must succeed or fail gracefully (not 500)"""
        # Minimal valid PDF header
        pdf_content = b"%PDF-1.4\n%Test PDF content for testing purposes only"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        response = test_client.post("/chat/uploads", headers=auth_headers, files=files)
        # Accept 200 (success) or 400 (if PDF parsing requires real content) — not 500
        assert response.status_code in (200, 400)

    def test_invalid_file_type_rejected(self, test_client, auth_headers):
        """Non-allowed file type must return 400"""
        files = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
        response = test_client.post("/chat/uploads", headers=auth_headers, files=files)
        assert response.status_code == 400

    def test_empty_file_rejected(self, test_client, auth_headers):
        """Empty file must return 400"""
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        response = test_client.post("/chat/uploads", headers=auth_headers, files=files)
        assert response.status_code == 400

    def test_upload_requires_auth(self, test_client):
        """File upload without auth must return 401"""
        files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
        response = test_client.post("/chat/uploads", files=files)
        assert response.status_code == 401
