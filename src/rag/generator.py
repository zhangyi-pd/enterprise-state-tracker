"""Generator — 基于 DeepSeek API 的 RAG 生成器，支持引用溯源。"""
import json
import requests
from typing import List, Dict, Any
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, LLM_MODEL


RAG_PROMPT = """You are an enterprise document analyst. Answer the user's question based ONLY on the provided context documents.

For each factual claim in your answer, cite the source document in brackets like [filename].

If the context does not contain enough information to answer, say "I cannot find enough information in the provided documents."

Context documents:
---
{context}
---

Question: {question}

Answer (with citations):"""


def generate_answer(question: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """根据检索到的文档块生成带引用的回答。"""
    # 构建上下文文本
    context_parts = []
    source_map = {}
    for i, result in enumerate(context_chunks):
        chunk = result["chunk"]
        source = chunk["source"]
        text = chunk["text"]
        # 截断过长的块
        if len(text) > 3000:
            text = text[:1500] + "\n[...]" + text[-1500:]
        context_parts.append("[Doc " + str(i + 1) + "] " + source + "\n" + text)
        source_map[str(i + 1)] = {
            "source": source,
            "score": result.get("score", 0),
            "text_preview": text[:200],
        }
    
    context = "\n\n---\n\n".join(context_parts)
    prompt = RAG_PROMPT.format(context=context, question=question)
    
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are an enterprise document analyst. Answer based on context with citations."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }
    
    headers = {
        "Authorization": "Bearer " + DEEPSEEK_API_KEY,
        "Content-Type": "application/json",
    }
    
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        answer = result["choices"][0]["message"]["content"].strip()
        
        return {
            "question": question,
            "answer": answer,
            "sources": source_map,
            "context_count": len(context_chunks),
            "success": True,
        }
    except Exception as e:
        return {
            "question": question,
            "answer": "",
            "error": str(e),
            "success": False,
        }
