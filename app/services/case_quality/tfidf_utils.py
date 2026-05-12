"""轻量级 TF-IDF 向量化与余弦相似度工具 - 替代 SequenceMatcher 实现更精准的冗余检测。

依赖: numpy（已在 requirements.txt 中）
安装命令: pip install numpy==1.26.4

设计决策:
    - 不依赖 scikit-learn，仅使用 numpy 实现完整 TF-IDF 流程
    - 中文文本采用字符 bigram 分词，英文按空白分词，兼顾中英混合场景
    - 阈值按项目规模动态调整，避免小项目误杀、大项目漏检
"""
import math
import re
from typing import Dict, List, Optional, Tuple

import numpy as np


def tokenize(text: str) -> List[str]:
    """将文本拆分为 token 列表，支持中英混合。

    策略: 英文按空白分词后取 lowercase，中文逐字符取 bigram，
    两者合并作为最终 token 集合。

    Args:
        text: 原始文本。

    Returns:
        List[str]: token 列表。
    """
    if not text or not text.strip():
        return []

    normalized = text.strip().lower()
    tokens: List[str] = []

    # 英文单词分词
    englishWords = re.findall(r'[a-z0-9]+', normalized)
    tokens.extend(englishWords)

    # 中文字符 bigram
    chineseChars = re.findall(r'[\u4e00-\u9fff]', normalized)
    for i in range(len(chineseChars) - 1):
        tokens.append(chineseChars[i] + chineseChars[i + 1])
    # 单字也保留（短文本兜底）
    if len(chineseChars) <= 1:
        tokens.extend(chineseChars)

    return tokens


class LightweightTfidfVectorizer:
    """轻量级 TF-IDF 向量化器 - 基于 numpy 实现，无需 scikit-learn。

    用法::

        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["文档1 文本", "文档2 文本"])
        # matrix.shape == (2, vocab_size)
    """

    def __init__(self, maxFeatures: Optional[int] = 5000) -> None:
        """初始化向量化器。

        Args:
            maxFeatures: 保留的最大特征数，按 IDF 方差排序取前 N。None 表示不限制。
        """
        self.maxFeatures = maxFeatures
        self.vocabulary_: Dict[str, int] = {}
        self.idf_: Optional[np.ndarray] = None

    def fit_transform(self, documents: List[str]) -> np.ndarray:
        """拟合词汇表并返回 TF-IDF 矩阵。

        Args:
            documents: 文档列表，每个元素为一段文本。

        Returns:
            np.ndarray: TF-IDF 矩阵，shape=(n_docs, n_features)。
        """
        if not documents:
            return np.array([], dtype=np.float64).reshape(0, 0)

        # Step 1: 分词
        tokenizedDocs: List[List[str]] = [tokenize(doc) for doc in documents]

        # Step 2: 构建词汇表
        termDocCount: Dict[str, int] = {}
        for docTokens in tokenizedDocs:
            uniqueTokens = set(docTokens)
            for token in uniqueTokens:
                termDocCount[token] = termDocCount.get(token, 0) + 1

        # 按特征重要性筛选
        if self.maxFeatures and len(termDocCount) > self.maxFeatures:
            # IDF 方差越大越有区分度，优先保留
            nDocs = len(documents)
            scoredTerms = [
                (term, count, abs(math.log(nDocs / (1 + count)) - math.log(nDocs / (1 + nDocs / 2))))
                for term, count in termDocCount.items()
            ]
            scoredTerms.sort(key=lambda x: x[2], reverse=True)
            termDocCount = {term: count for term, count, _ in scoredTerms[:self.maxFeatures]}

        self.vocabulary_ = {term: idx for idx, term in enumerate(sorted(termDocCount.keys()))}
        vocabSize = len(self.vocabulary_)

        if vocabSize == 0:
            self.idf_ = np.array([], dtype=np.float64)
            return np.zeros((len(documents), 0), dtype=np.float64)

        # Step 3: 计算 IDF
        nDocs = len(documents)
        self.idf_ = np.zeros(vocabSize, dtype=np.float64)
        for term, idx in self.vocabulary_.items():
            df = termDocCount[term]
            self.idf_[idx] = math.log((1 + nDocs) / (1 + df)) + 1  # 平滑 IDF

        # Step 4: 计算 TF-IDF 矩阵
        tfidfMatrix = np.zeros((nDocs, vocabSize), dtype=np.float64)
        for docIdx, docTokens in enumerate(tokenizedDocs):
            if not docTokens:
                continue
            # TF: 词频 / 文档总词数
            termFreq: Dict[str, int] = {}
            for token in docTokens:
                termFreq[token] = termFreq.get(token, 0) + 1
            totalTerms = len(docTokens)
            for term, freq in termFreq.items():
                if term in self.vocabulary_:
                    colIdx = self.vocabulary_[term]
                    tfidfMatrix[docIdx, colIdx] = (freq / totalTerms) * self.idf_[colIdx]

        # L2 归一化（每行向量归一化，便于余弦相似度计算）
        rowNorms = np.linalg.norm(tfidfMatrix, axis=1, keepdims=True)
        rowNorms = np.where(rowNorms == 0, 1.0, rowNorms)
        tfidfMatrix = tfidfMatrix / rowNorms

        return tfidfMatrix

    def transform(self, documents: List[str]) -> np.ndarray:
        """使用已拟合的词汇表将新文档转换为 TF-IDF 矩阵。

        Args:
            documents: 文档列表。

        Returns:
            np.ndarray: TF-IDF 矩阵。

        Raises:
            RuntimeError: 向量化器尚未拟合。
        """
        if self.idf_ is None or not self.vocabulary_:
            raise RuntimeError("向量化器尚未拟合，请先调用 fit_transform")

        vocabSize = len(self.vocabulary_)
        nDocs = len(documents)
        tfidfMatrix = np.zeros((nDocs, vocabSize), dtype=np.float64)

        for docIdx, doc in enumerate(documents):
            docTokens = tokenize(doc)
            if not docTokens:
                continue
            termFreq: Dict[str, int] = {}
            for token in docTokens:
                termFreq[token] = termFreq.get(token, 0) + 1
            totalTerms = len(docTokens)
            for term, freq in termFreq.items():
                if term in self.vocabulary_:
                    colIdx = self.vocabulary_[term]
                    tfidfMatrix[docIdx, colIdx] = (freq / totalTerms) * self.idf_[colIdx]

        # L2 归一化
        rowNorms = np.linalg.norm(tfidfMatrix, axis=1, keepdims=True)
        rowNorms = np.where(rowNorms == 0, 1.0, rowNorms)
        tfidfMatrix = tfidfMatrix / rowNorms

        return tfidfMatrix


def cosineSimilarity(vecA: np.ndarray, vecB: np.ndarray) -> float:
    """计算两个向量的余弦相似度。

    由于 TF-IDF 向量已做 L2 归一化，余弦相似度等于点积。

    Args:
        vecA: 向量 A。
        vecB: 向量 B。

    Returns:
        float: 余弦相似度，范围 [0.0, 1.0]。
    """
    if vecA.size == 0 or vecB.size == 0:
        return 0.0
    normA = np.linalg.norm(vecA)
    normB = np.linalg.norm(vecB)
    if normA < 1e-10 or normB < 1e-10:
        return 0.0
    return float(np.dot(vecA, vecB) / (normA * normB))


def cosineSimilarityMatrix(matrix: np.ndarray) -> np.ndarray:
    """计算 TF-IDF 矩阵中所有行向量两两之间的余弦相似度。

    利用矩阵乘法批量计算，时间复杂度 O(n^2 * d)。

    Args:
        matrix: TF-IDF 矩阵，shape=(n_docs, n_features)，已 L2 归一化。

    Returns:
        np.ndarray: 相似度矩阵，shape=(n_docs, n_docs)。
    """
    if matrix.size == 0:
        return np.array([], dtype=np.float64).reshape(0, 0)
    # 已 L2 归一化，余弦相似度 = 矩阵乘自身转置
    simMatrix = matrix @ matrix.T
    # 裁剪浮点误差
    np.clip(simMatrix, 0.0, 1.0, out=simMatrix)
    return simMatrix


def computeDynamicThreshold(totalCases: int) -> float:
    """根据项目用例规模动态计算相似度阈值。

    核心思路: 用例少时阈值高（避免误杀），用例多时阈值低（避免漏检）。
    采用分段线性插值，确保阈值在 [0.55, 0.85] 区间内平滑变化。

    分段规则:
        - totalCases <= 10:  0.85  （极小项目，几乎不判冗余）
        - totalCases <= 30:  0.78  （小型项目）
        - totalCases <= 100: 0.70  （中型项目）
        - totalCases <= 300: 0.62  （大型项目）
        - totalCases > 300:  0.55  （超大型项目）

    Args:
        totalCases: 项目中用例总数。

    Returns:
        float: 动态阈值，范围 [0.55, 0.85]。
    """
    # (用例数上界, 阈值) 分段表，按用例数升序排列
    segments: List[Tuple[int, float]] = [
        (10, 0.85),
        (30, 0.78),
        (100, 0.70),
        (300, 0.62),
        (float('inf'), 0.55),
    ]

    prevBound = 0
    prevThreshold = 0.85
    for bound, threshold in segments:
        if totalCases <= bound:
            # 线性插值
            if bound == prevBound:
                return threshold
            ratio = (totalCases - prevBound) / (bound - prevBound)
            interpolated = prevThreshold + ratio * (threshold - prevThreshold)
            return round(interpolated, 4)
        prevBound = bound
        prevThreshold = threshold

    return 0.55


def batchComputeSimilarity(
    targetTexts: List[str],
    candidateTexts: List[str],
) -> np.ndarray:
    """批量计算目标文档与候选文档之间的 TF-IDF 余弦相似度。

    将目标和候选合并构建统一词汇表，确保向量空间一致。

    Args:
        targetTexts: 目标文档文本列表。
        candidateTexts: 候选文档文本列表。

    Returns:
        np.ndarray: 相似度矩阵，shape=(n_targets, n_candidates)。
    """
    if not targetTexts or not candidateTexts:
        return np.array([], dtype=np.float64).reshape(
            len(targetTexts), len(candidateTexts)
        )

    # 合并所有文档构建统一词汇表
    allDocs = targetTexts + candidateTexts
    vectorizer = LightweightTfidfVectorizer()
    tfidfMatrix = vectorizer.fit_transform(allDocs)

    if tfidfMatrix.shape[1] == 0:
        return np.zeros((len(targetTexts), len(candidateTexts)), dtype=np.float64)

    nTargets = len(targetTexts)
    targetMatrix = tfidfMatrix[:nTargets]
    candidateMatrix = tfidfMatrix[nTargets:]

    # 已 L2 归一化，余弦相似度 = 矩阵乘法
    simMatrix = targetMatrix @ candidateMatrix.T
    np.clip(simMatrix, 0.0, 1.0, out=simMatrix)

    return simMatrix
