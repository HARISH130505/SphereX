"""
Application error definitions and HTTP exception helpers.
"""
from fastapi import HTTPException

class NotFoundError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=404, detail=detail)

class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=detail)

class ArchiveError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=502, detail=detail)
