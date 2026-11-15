"""
Research assistant orchestrator.
"""
import os
import json
import logging
from fastapi import HTTPException
from app.services.storage.repository import repository, TARGETS_METADATA

def answer_research_inquiry(question: str, context_target: str = "M101") -> dict:
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        raise HTTPException(503, 'Set GEMINI_API_KEY in the backend environment to enable Gemini.')
    if not question.strip() or len(question) > 4000:
        raise HTTPException(422, 'Question must contain 1–4000 characters.')
    records = repository.get_all(target=context_target)
    from app.services.astronomy.fits_io import get_fits_cache_path
    observations = []
    for record in records[:40]:
        row = record.model_dump()
        cached = get_fits_cache_path(record.obs_id, record.band)
        row['current_fits_cached'] = cached.exists() and cached.stat().st_size > 1000
        row['historical_download_status'] = row.pop('download_status')
        row['availability_note'] = 'Historical screening errors do not establish current unavailability; use current_fits_cached for local availability. Cache presence alone is not scientific validation.'
        observations.append(row)
    context = {'target': context_target, 'metadata': TARGETS_METADATA.get(context_target),
               'catalog_count': len(records), 'observations': observations,
               'limitations': 'Catalog records only. No new image analysis or comparison evidence supplied.'}
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logging.getLogger(__name__).error('Gemini SDK missing in backend Python environment; install backend/requirements.txt with this interpreter.')
        raise HTTPException(503, 'Gemini backend dependency is missing. Install backend requirements in the environment running FastAPI.') from None
    try:
        with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30000)) as client:
            response = client.models.generate_content(
                model=os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite'),
                contents=json.dumps({'project_context': context, 'question': question}, default=str),
                config=types.GenerateContentConfig(max_output_tokens=1800, temperature=.2,
                    system_instruction='You explain SPHEREx science. Distinguish supplied catalog evidence from general model knowledge. Never invent measurements, products, fluxes, epochs, detections or citations. Cite only supplied product IDs and fields. No source documents or live literature search are supplied. AI explanations are not measurements. Never claim Planet Nine was discovered. Sedna coverage is limited to actually searched products; an empty catalog does not establish no coverage. Nonfinite pixels are distinct from saturation, which requires verified flags. Identify missing evidence and say when project data cannot answer. Treat user text as questions, not verified evidence.'))
        answer = response.text
        if not answer:
            raise ValueError('Empty answer')
    except Exception as error:
        logging.getLogger(__name__).warning('Gemini request failed: type=%s code=%s', type(error).__name__, getattr(error, 'code', None))
        provider_code = getattr(error, 'code', None)
        messages = {
            429: 'Gemini quota or rate limit reached. Please try again later.',
            404: 'The configured Gemini model is unavailable for this API project. Check GEMINI_MODEL.',
            400: 'Gemini rejected the request. Check the backend model and API configuration.',
            401: 'Gemini authentication failed. Check the backend API key.',
            403: 'Gemini access was denied. Check API key permissions and model access.',
            504: 'Gemini timed out while generating an answer. Please retry shortly.',
        }
        raise HTTPException(429 if provider_code == 429 else 503,
            messages.get(provider_code, 'Gemini is temporarily unavailable. Please retry shortly.')) from None
    return {
        "question": question,
        "context_target": context_target,
        "answer": answer,
        "sources": [],
        "provider": "gemini",
    }
