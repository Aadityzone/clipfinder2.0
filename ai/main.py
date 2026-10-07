from fastapi import FastAPI
from pydantic import BaseModel

app=FastAPI(title="Clip Finder AI",version="2.0.0")

class Health(BaseModel):
    ok: bool
    service: str
    version: str

@app.get("/health",response_model=Health)
def health():
    return Health(ok=True,service="ai",version="2.0.0")