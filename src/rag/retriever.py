"""Retriever — 基于 TF-IDF + 余弦相似的本地检索器（纯 numpy，无需 ML 模型）。"""
import re
import math
import numpy as np
from collections import Counter
from typing import List, Dict, Any


def _tokenize(text: str) -> List[str]:
    """分词：小写 + 按非字母字符分割，过滤短词。"""
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return tokens


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """计算词频 (TF)。"""
    total = len(tokens)
    if total == 0:
        return {}
    counts = Counter(tokens)
    return {word: count / total for word, count in counts.items()}


class TFIDFRetriever:
    """本地 TF-IDF 检索器。"""
    
    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.doc_tfidf: List[Dict[str, float]] = []
        self.idf: Dict[str, float] = {}
        self.vocab: set = set()
    
    def add_chunks(self, chunks: List[Dict[str, Any]]):
        """添加文档块到索引。"""
        start_idx = len(self.chunks)
        self.chunks.extend(chunks)
        
        # 计算所有文档的 TF
        doc_tfs = []
        all_tokens = []
        for chunk in chunks:
            tokens = _tokenize(chunk["text"])
            all_tokens.extend(tokens)
            doc_tfs.append(_compute_tf(tokens))
        
        # 计算 IDF
        doc_count = len(chunks)
        term_doc_freq = Counter()
        for tf in doc_tfs:
            for word in tf:
                term_doc_freq[word] += 1
        
        self.idf = {}
        for word, freq in term_doc_freq.items():
            self.idf[word] = math.log((doc_count + 1) / (freq + 1)) + 1
        
        # 计算 TF-IDF
        for tf in doc_tfs:
            doc_tfidf = {}
            for word, tf_val in tf.items():
                doc_tfidf[word] = tf_val * self.idf.get(word, 1)
            self.doc_tfidf.append(doc_tfidf)
        
        self.vocab.update(all_tokens)
    
    def _tfidf_vector(self, tfidf: Dict[str, float]) -> np.ndarray:
        """将 TF-IDF dict 转为固定长度向量。"""
        vocab_list = sorted(self.vocab)
        vec = np.zeros(len(vocab_list), dtype=np.float32)
        for i, word in enumerate(vocab_list):
            vec[i] = tfidf.get(word, 0.0)
        return vec
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索最相关的文档块。"""
        if not self.chunks:
            return []
        
        query_tokens = _tokenize(query)
        query_tf = _compute_tf(query_tokens)
        query_tfidf = {}
        for word, tf_val in query_tf.items():
            query_tfidf[word] = tf_val * self.idf.get(word, 1)
        
        query_vec = self._tfidf_vector(query_tfidf)
        
        # 计算余弦相似度
        scores = []
        for doc_tfidf in self.doc_tfidf:
            doc_vec = self._tfidf_vector(doc_tfidf)
            norm_q = np.linalg.norm(query_vec)
            norm_d = np.linalg.norm(doc_vec)
            if norm_q == 0 or norm_d == 0:
                scores.append(0.0)
            else:
                scores.append(float(np.dot(query_vec, doc_vec) / (norm_q * norm_d)))
        
        # 取 top_k
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "chunk": self.chunks[idx],
                    "score": round(scores[idx], 4),
                    "index": idx,
                })
        return results
