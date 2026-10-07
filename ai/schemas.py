from pydantic import BaseModel, Field
class TranscribeRequest(BaseModel):
    media_path: str
    language: str | None = None
class Word(BaseModel):
    start: float
    end: float
    word: str
    confidence: float | None = None
class Segment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float | None = None
    words: list[Word] = Field(default_factory=list)
class TranscribeResponse(BaseModel):
    language: str
    text: str
    segments: list[Segment]
    duration: float
