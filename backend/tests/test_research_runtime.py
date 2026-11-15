"""Dependency failures must be actionable without leaking backend credentials."""
import builtins
import pytest
from fastapi import HTTPException
from app.services.research.assistant import answer_research_inquiry


def test_missing_gemini_sdk_is_reported_explicitly(monkeypatch, caplog):
    monkeypatch.setenv('GEMINI_API_KEY', 'private-test-key')
    original_import = builtins.__import__
    def import_without_genai(name, *args, **kwargs):
        if name == 'google' or name.startswith('google.genai'):
            raise ModuleNotFoundError('No module named google')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', import_without_genai)
    with pytest.raises(HTTPException) as caught:
        answer_research_inquiry('What is M101?', 'M101')
    assert caught.value.status_code == 503
    assert 'dependency is missing' in caught.value.detail
    assert 'SDK missing' in caplog.text
    assert 'private-test-key' not in caplog.text + caught.value.detail
