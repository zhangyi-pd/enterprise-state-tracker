"""RAG API — FastAPI 接口，提供文档问答能力。"""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from src.rag.engine import RAGEngine, get_engine

app = FastAPI(title="Enterprise RAG - Document Q&A")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# 初始化 RAG 引擎
engine = get_engine()


@app.on_event("startup")
async def startup():
    """启动时初始化 RAG 引擎（如未初始化）。"""
    if not engine.initialized:
        engine.initialize()


@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    status = "ready" if engine.initialized else "not initialized"
    stats = {}
    if engine.initialized:
        stats = {
            "chunks": len(engine.retriever.chunks),
            "vocab": len(engine.retriever.vocab),
        }
    return templates.TemplateResponse("rag_chat.html", {
        "request": request,
        "status": status,
        "stats": stats,
    })


@app.post("/api/query")
async def api_query(request: Request):
    """RAG 问答 API。"""
    data = await request.json()
    question = data.get("question", "").strip()
    top_k = data.get("top_k", 5)

    if not question:
        return JSONResponse({"error": "Question is required"}, status_code=400)

    if not engine.initialized:
        return JSONResponse({"error": "Engine not initialized"}, status_code=503)

    result = engine.query(question, top_k=top_k)
    return JSONResponse(result)


@app.get("/api/search")
async def api_search(q: str = "", top_k: int = 5):
    """仅检索，不生成（用于调试）。"""
    if not q:
        return JSONResponse({"error": "Query parameter 'q' is required"}, status_code=400)
    results = engine.search_only(q, top_k=top_k)
    return JSONResponse({
        "results": [
            {"source": r["chunk"]["source"], "score": r["score"],
             "text": r["chunk"]["text"][:300]}
            for r in results
        ]
    })


if __name__ == "__main__":
    import uvicorn
    engine.initialize()
    print("RAG API: http://127.0.0.1:8085")
    uvicorn.run(app, host="127.0.0.1", port=8085, log_level="warning")