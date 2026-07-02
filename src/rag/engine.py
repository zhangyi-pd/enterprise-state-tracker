"""RAG Engine — 端到端 RAG 管道：建索引 → 检索 → 生成。"""
import os
import json
from typing import List, Dict, Any, Optional
from config import FILINGS_DIR
from .chunker import chunk_all_filings
from .retriever import TFIDFRetriever
from .generator import generate_answer


class RAGEngine:
    """RAG 引擎：加载文档 → 构建索引 → 问答。"""
    
    def __init__(self):
        self.retriever = TFIDFRetriever()
        self.initialized = False
    
    def initialize(self, filings_dir: Optional[str] = None):
        """初始化：加载申报文件并构建索引。"""
        if filings_dir is None:
            filings_dir = str(FILINGS_DIR)
        
        print("=" * 50)
        print("  RAG Engine 初始化")
        print("=" * 50)
        
        # 分块
        print("[1/2] 分块文档...")
        chunks = chunk_all_filings(filings_dir)
        print("  共 " + str(len(chunks)) + " 个块")
        
        # 构建 TF-IDF 索引
        print("[2/2] 构建检索索引...")
        self.retriever.add_chunks(chunks)
        print("  词汇表大小: " + str(len(self.retriever.vocab)) + " 个词")
        
        self.initialized = True
        print("=" * 50)
        print("  RAG Engine 就绪")
        print("=" * 50)
    
    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        """问答：检索 → 生成。"""
        if not self.initialized:
            return {"question": question, "answer": "Engine not initialized.", "success": False}
        
        # 检索
        results = self.retriever.search(question, top_k=top_k)
        if not results:
            return {
                "question": question,
                "answer": "No relevant documents found.",
                "sources": [],
                "success": True,
            }
        
        # 生成
        answer = generate_answer(question, results)
        answer["retrieved_chunks"] = [
            {"source": r["chunk"]["source"], "score": r["score"]}
            for r in results
        ]
        return answer
    
    def search_only(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """仅检索，不生成（用于调试）。"""
        return self.retriever.search(question, top_k=top_k)


# 全局单例
_engine = None


def get_engine() -> RAGEngine:
    """获取全局 RAG 引擎实例。"""
    global _engine
    if _engine is None:
        _engine = RAGEngine()
    return _engine


if __name__ == "__main__":
    engine = get_engine()
    engine.initialize()
    
    # 测试问答
    questions = [
        "What are Microsoft's main risk factors?",
        "How has Microsoft's AI strategy evolved?",
        "What is Amazon's approach to cloud computing?",
    ]
    for q in questions:
        print("\n" + "=" * 50)
        print("Q: " + q)
        result = engine.query(q)
        if result["success"]:
            print("\nA: " + result["answer"][:300])
            print("\n来源:")
            for s in result.get("retrieved_chunks", []):
                print("  - " + s["source"] + " (score: " + str(s["score"]) + ")")
        else:
            print("Error: " + result.get("error", "unknown"))
