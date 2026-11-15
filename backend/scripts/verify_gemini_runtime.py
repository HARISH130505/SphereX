"""Sanitized live verification using the interpreter running this script."""
import os
import sys
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)
    model=os.getenv('GEMINI_MODEL','gemini-3.1-flash-lite')
    key=os.getenv('GEMINI_API_KEY','').strip()
    print({'python':sys.executable,'model':model,'key_configured':bool(key)},flush=True)
    from google import genai
    from google.genai import types
    started=time.monotonic()
    try:
        with genai.Client(api_key=key,http_options=types.HttpOptions(timeout=30000)) as client:
            response=client.models.generate_content(model=model,contents='Reply with exactly: GEMINI_OK')
        print({'direct':'PASS' if response.text.strip()=='GEMINI_OK' else 'FAIL','seconds':round(time.monotonic()-started,2)},flush=True)
    except Exception as error:
        print({'direct':'FAIL','category':type(error).__name__,'code':getattr(error,'code',None),'seconds':round(time.monotonic()-started,2)},flush=True)
    for port in (8000,3000):
        started=time.monotonic()
        response=requests.post(f'http://127.0.0.1:{port}/api/research/ask',json={
            'question':'What is M101? Distinguish project observations from general astronomical knowledge.',
            'context_target':'M101'},timeout=45)
        data=response.json()
        print({'port':port,'http_status':response.status_code,'provider':data.get('provider'),
               'answer_nonempty':bool(data.get('answer')),'context_target':data.get('context_target'),
               'seconds':round(time.monotonic()-started,2),'error':data.get('detail')},flush=True)

if __name__=='__main__': main()
