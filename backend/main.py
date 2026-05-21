from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.core.case_analyzer import CaseAnalyzer


app = FastAPI()
case_analyzer = CaseAnalyzer()


class EchoRequest(BaseModel):
    text: str


class AnalyzeRequest(BaseModel):
    customer_text: str
    ocr_text: str | None = None
    selected_style: str | None = None


@app.get("/")
def root():
    return {"message": "FastAPI is working"}


@app.get("/status")
def status():
    return {
        "app": "Local Support AI backend",
        "status": "ok",
        "mode": "learning",
    }


@app.post("/echo")
def echo(data: EchoRequest):
    return {
        "original_text": data.text,
        "length": len(data.text),
        "message": "POST endpoint received your text",
    }


@app.post("/analyze-request")
def analyze_request(data: AnalyzeRequest):
    analysis = case_analyzer.analyze(
        data.customer_text,
        data.ocr_text or "",
    )

    return {
        "customer_text": data.customer_text,
        "ocr_text": data.ocr_text,
        "selected_style": data.selected_style,
        "topic": analysis.topic,
        "signals": analysis.signals,
        "extracted": analysis.extracted,
    }
