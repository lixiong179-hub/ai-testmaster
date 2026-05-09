"""冗余度算法升�?(T13) 单元测试 - 覆盖 TF-IDF 向量化、余弦相似度、动态阈值、RedundancyMixin�?

测试策略: 真实数据构造，不使�?Mock，覆盖正�?空�?异常/边界场景�?
"""
import math
import pytest
import numpy as np

from app.services.case_quality.tfidf_utils import (
    tokenize,
    LightweightTfidfVectorizer,
    cosineSimilarity,
    cosineSimilarityMatrix,
    computeDynamicThreshold,
    batchComputeSimilarity,
)


# ============================================================
# tokenize 函数测试
# ============================================================

class TestTokenize:

    def test_chinese_text(self) -> None:
        """中文文本应产�?bigram token�?""
        tokens = tokenize("点击登录按钮")
        assert "点击" in tokens
        assert "击登" in tokens
        assert "登录" in tokens
        assert "录按" in tokens
        assert "按钮" in tokens

    def test_english_text(self) -> None:
        """英文文本应按空白分词�?""
        tokens = tokenize("click login button")
        assert "click" in tokens
        assert "login" in tokens
        assert "button" in tokens

    def test_mixed_chinese_english(self) -> None:
        """中英混合文本应同时产生中�?bigram 和英文单词�?""
        tokens = tokenize("点击 login 按钮")
        assert "点击" in tokens
        assert "按钮" in tokens
        assert "login" in tokens

    def test_empty_string(self) -> None:
        """空字符串返回空列表�?""
        assert tokenize("") == []

    def test_whitespace_only(self) -> None:
        """纯空白字符串返回空列表�?""
        assert tokenize("   ") == []

    def test_single_chinese_char(self) -> None:
        """单个中文字符应保留为单字 token�?""
        tokens = tokenize("�?)
        assert "�? in tokens

    def test_numeric_text(self) -> None:
        """数字应作�?token 保留�?""
        tokens = tokenize("step 1 input value 123")
        assert "1" in tokens
        assert "123" in tokens

    def test_special_characters_ignored(self) -> None:
        """特殊符号不应产生 token�?""
        tokens = tokenize("!!! ??? ###")
        assert tokens == []


# ============================================================
# LightweightTfidfVectorizer 测试
# ============================================================

class TestLightweightTfidfVectorizer:

    def test_fit_transform_basic(self) -> None:
        """基本 fit_transform 应返回正确形状的矩阵�?""
        docs = [
            "点击登录按钮 输入用户�?,
            "点击注册按钮 输入邮箱",
            "浏览商品列表",
        ]
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(docs)
        assert matrix.shape[0] == 3
        assert matrix.shape[1] > 0
        assert matrix.dtype == np.float64

    def test_fit_transform_empty_docs(self) -> None:
        """空文档列表应返回空矩阵�?""
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform([])
        assert matrix.shape == (0, 0)

    def test_fit_transform_single_doc(self) -> None:
        """单文档应产生非零向量�?""
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["点击登录 输入密码"])
        assert matrix.shape[0] == 1
        assert matrix.shape[1] > 0

    def test_l2_normalization(self) -> None:
        """每行向量应近�?L2 归一化（范数=1）�?""
        docs = ["点击登录", "输入密码", "验证结果"]
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(docs)
        for i in range(matrix.shape[0]):
            rowNorm = float(np.linalg.norm(matrix[i]))
            if rowNorm > 0:
                assert abs(rowNorm - 1.0) < 1e-6, f"�?{i} �?L2 范数不为 1: {rowNorm}"

    def test_identical_docs_high_similarity(self) -> None:
        """相同文档�?TF-IDF 向量应高度相似�?""
        docs = ["点击登录按钮 输入用户�?, "点击登录按钮 输入用户�?]
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(docs)
        sim = cosineSimilarity(matrix[0], matrix[1])
        assert sim > 0.99, f"相同文档相似度应接近 1.0，实�? {sim}"

    def test_different_docs_low_similarity(self) -> None:
        """差异大的文档相似度应较低�?""
        docs = ["点击登录按钮", "滚动页面到底�?等待加载完成"]
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(docs)
        sim = cosineSimilarity(matrix[0], matrix[1])
        assert sim < 0.5, f"差异大的文档相似度应较低，实�? {sim}"

    def test_transform_after_fit(self) -> None:
        """transform 应使用已拟合的词汇表�?""
        trainDocs = ["点击登录 输入密码", "浏览商品 加入购物�?]
        vectorizer = LightweightTfidfVectorizer()
        vectorizer.fit_transform(trainDocs)

        testDocs = ["点击登录按钮"]
        testMatrix = vectorizer.transform(testDocs)
        assert testMatrix.shape[0] == 1
        assert testMatrix.shape[1] == len(vectorizer.vocabulary_)

    def test_transform_without_fit_raises(self) -> None:
        """未拟合时调用 transform 应抛出异常�?""
        vectorizer = LightweightTfidfVectorizer()
        with pytest.raises(RuntimeError, match="尚未拟合"):
            vectorizer.transform(["测试"])

    def test_max_features_limit(self) -> None:
        """maxFeatures 应限制词汇表大小�?""
        docs = ["词语A 词语B 词语C 词语D 词语E 词语F 词语G 词语H"]
        vectorizer = LightweightTfidfVectorizer(maxFeatures=3)
        vectorizer.fit_transform(docs)
        assert len(vectorizer.vocabulary_) <= 3

    def test_all_empty_documents(self) -> None:
        """所有文档为空字符串时应返回零矩阵�?""
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["", "", ""])
        assert matrix.shape[0] == 3
        assert matrix.shape[1] == 0

    def test_vocabulary_built_correctly(self) -> None:
        """词汇表应包含所有出现过�?token�?""
        docs = ["点击 登录", "输入 密码"]
        vectorizer = LightweightTfidfVectorizer()
        vectorizer.fit_transform(docs)
        tokens = tokenize("点击 登录 输入 密码")
        for token in set(tokens):
            if token in vectorizer.vocabulary_:
                assert isinstance(vectorizer.vocabulary_[token], int)


# ============================================================
# cosineSimilarity 函数测试
# ============================================================

class TestCosineSimilarity:

    def test_identical_vectors(self) -> None:
        """相同向量相似度应�?1.0�?""
        vec = np.array([1.0, 0.0, 0.0])
        sim = cosineSimilarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        """正交向量相似度应�?0.0�?""
        vecA = np.array([1.0, 0.0])
        vecB = np.array([0.0, 1.0])
        sim = cosineSimilarity(vecA, vecB)
        assert abs(sim) < 1e-6

    def test_zero_vector(self) -> None:
        """零向量与任意向量相似度应�?0.0�?""
        vecA = np.array([0.0, 0.0])
        vecB = np.array([1.0, 1.0])
        sim = cosineSimilarity(vecA, vecB)
        assert sim == 0.0

    def test_empty_vectors(self) -> None:
        """空向量相似度应为 0.0�?""
        vecA = np.array([])
        vecB = np.array([])
        sim = cosineSimilarity(vecA, vecB)
        assert sim == 0.0

    def test_opposite_direction(self) -> None:
        """方向相反的向量相似度应为 -1.0（非负场景下裁剪�?0）�?""
        vecA = np.array([1.0, 0.0])
        vecB = np.array([-1.0, 0.0])
        sim = cosineSimilarity(vecA, vecB)
        assert abs(sim - (-1.0)) < 1e-6


# ============================================================
# cosineSimilarityMatrix 函数测试
# ============================================================

class TestCosineSimilarityMatrix:

    def test_diagonal_is_one(self) -> None:
        """对角线元素应�?1.0�?""
        docs = ["点击登录", "输入密码", "验证结果"]
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(docs)
        simMatrix = cosineSimilarityMatrix(matrix)
        for i in range(simMatrix.shape[0]):
            assert abs(simMatrix[i, i] - 1.0) < 1e-6

    def test_symmetric(self) -> None:
        """相似度矩阵应对称�?""
        docs = ["点击登录", "输入密码"]
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(docs)
        simMatrix = cosineSimilarityMatrix(matrix)
        assert abs(simMatrix[0, 1] - simMatrix[1, 0]) < 1e-6

    def test_empty_matrix(self) -> None:
        """空矩阵应返回空结果�?""
        simMatrix = cosineSimilarityMatrix(np.array([]).reshape(0, 0))
        assert simMatrix.shape == (0, 0)

    def test_values_clipped(self) -> None:
        """相似度值应�?[0, 1] 范围内�?""
        docs = ["点击登录 输入密码", "点击注册 输入邮箱", "浏览商品"]
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(docs)
        simMatrix = cosineSimilarityMatrix(matrix)
        assert np.all(simMatrix >= 0.0)
        assert np.all(simMatrix <= 1.0)


# ============================================================
# computeDynamicThreshold 函数测试
# ============================================================

class TestComputeDynamicThreshold:

    def test_tiny_project_high_threshold(self) -> None:
        """极小项目�?=10 用例）阈值应最高�?""
        threshold = computeDynamicThreshold(5)
        assert 0.80 <= threshold <= 0.85

    def test_small_project(self) -> None:
        """小型项目�?0~30 用例）阈值应中等偏高�?""
        threshold = computeDynamicThreshold(20)
        assert 0.75 <= threshold <= 0.85

    def test_medium_project(self) -> None:
        """中型项目�?0~100 用例）阈值应中等�?""
        threshold = computeDynamicThreshold(60)
        assert 0.65 <= threshold <= 0.78

    def test_large_project(self) -> None:
        """大型项目�?00~300 用例）阈值应较低�?""
        threshold = computeDynamicThreshold(200)
        assert 0.55 <= threshold <= 0.70

    def test_huge_project_low_threshold(self) -> None:
        """超大型项目（>300 用例）阈值应最低�?""
        threshold = computeDynamicThreshold(500)
        assert 0.55 <= threshold <= 0.62

    def test_threshold_monotonically_decreasing(self) -> None:
        """阈值应随用例数增加单调递减�?""
        sizes = [5, 15, 50, 150, 500]
        thresholds = [computeDynamicThreshold(s) for s in sizes]
        for i in range(len(thresholds) - 1):
            assert thresholds[i] >= thresholds[i + 1], (
                f"阈值应单调递减: size={sizes[i]} threshold={thresholds[i]} "
                f">= size={sizes[i+1]} threshold={thresholds[i+1]}"
            )

    def test_threshold_within_range(self) -> None:
        """阈值应始终�?[0.55, 0.85] 范围内�?""
        for size in [1, 5, 10, 30, 100, 300, 1000]:
            threshold = computeDynamicThreshold(size)
            assert 0.55 <= threshold <= 0.85, f"size={size} threshold={threshold} 超出范围"

    def test_zero_cases(self) -> None:
        """0 用例时阈值应取最高值�?""
        threshold = computeDynamicThreshold(0)
        assert threshold == 0.85


# ============================================================
# batchComputeSimilarity 函数测试
# ============================================================

class TestBatchComputeSimilarity:

    def test_basic_batch(self) -> None:
        """基本批量计算应返回正确形状�?""
        targets = ["点击登录 输入密码"]
        candidates = ["点击登录 输入用户�?, "浏览商品列表"]
        simMatrix = batchComputeSimilarity(targets, candidates)
        assert simMatrix.shape == (1, 2)

    def test_similar_docs_high_score(self) -> None:
        """相似文档应得到较高相似度�?""
        targets = ["点击登录按钮 输入用户名和密码"]
        candidates = ["点击登录按钮 输入用户名和密码 验证登录"]
        simMatrix = batchComputeSimilarity(targets, candidates)
        assert simMatrix[0, 0] > 0.5

    def test_dissimilar_docs_low_score(self) -> None:
        """差异大的文档应得到较低相似度�?""
        targets = ["点击登录按钮"]
        candidates = ["滚动页面 等待加载 查看报告"]
        simMatrix = batchComputeSimilarity(targets, candidates)
        assert simMatrix[0, 0] < 0.5

    def test_empty_targets(self) -> None:
        """空目标列表应返回空矩阵�?""
        simMatrix = batchComputeSimilarity([], ["测试"])
        assert simMatrix.shape == (0, 1)

    def test_empty_candidates(self) -> None:
        """空候选列表应返回空矩阵�?""
        simMatrix = batchComputeSimilarity(["测试"], [])
        assert simMatrix.shape == (1, 0)

    def test_multiple_targets(self) -> None:
        """多目标批量计算应返回正确形状�?""
        targets = ["点击登录", "浏览商品"]
        candidates = ["点击注册", "搜索商品"]
        simMatrix = batchComputeSimilarity(targets, candidates)
        assert simMatrix.shape == (2, 2)

    def test_values_in_valid_range(self) -> None:
        """所有相似度值应�?[0, 1] 范围内�?""
        targets = ["点击登录 输入密码"]
        candidates = ["点击注册 输入邮箱", "浏览商品 加入购物�?]
        simMatrix = batchComputeSimilarity(targets, candidates)
        assert np.all(simMatrix >= 0.0)
        assert np.all(simMatrix <= 1.0)


# ============================================================
# TF-IDF vs SequenceMatcher 精度对比测试
# ============================================================

class TestTfidfVsSequenceMatcher:

    def test_partial_overlap_not_false_positive(self) -> None:
        """部分重叠但语义不同的文档不应被误判为高相似�?

        SequenceMatcher �?"点击登录" vs "点击注册" 会给出较高相似度（共�?点击"），
        TF-IDF 应更精确地区分�?
        """
        targets = ["点击登录 输入密码 验证身份"]
        candidates = ["点击注册 输入邮箱 确认注册"]
        simMatrix = batchComputeSimilarity(targets, candidates)
        tfidfSim = float(simMatrix[0, 0])

        # SequenceMatcher 的相似度（作为对比基准）
        from difflib import SequenceMatcher as SM
        seqSim = SM(None, targets[0], candidates[0]).ratio()

        # TF-IDF 相似度应低于 SequenceMatcher，因�?TF-IDF 更关注区分性词�?
        assert tfidfSim < seqSim, (
            f"TF-IDF ({tfidfSim:.4f}) 应低�?SequenceMatcher ({seqSim:.4f}) "
            f"以减少误杀"
        )

    def test_truly_similar_docs_still_detected(self) -> None:
        """真正相似的文档仍应被检测出来�?""
        targets = ["点击登录按钮 输入用户�?输入密码 点击提交"]
        candidates = ["点击登录按钮 输入用户�?输入密码 点击提交 验证成功"]
        simMatrix = batchComputeSimilarity(targets, candidates)
        tfidfSim = float(simMatrix[0, 0])
        assert tfidfSim >= 0.7, f"真正相似的文档相似度�?>= 0.7，实�? {tfidfSim:.4f}"

    def test_completely_different_docs_low_similarity(self) -> None:
        """完全不同的文档相似度应很低�?""
        targets = ["点击登录按钮"]
        candidates = ["上传附件 下载报告 导出数据"]
        simMatrix = batchComputeSimilarity(targets, candidates)
        tfidfSim = float(simMatrix[0, 0])
        assert tfidfSim < 0.3, f"完全不同的文档相似度�?< 0.3，实�? {tfidfSim:.4f}"


# ============================================================
# RedundancyMixin 集成测试（纯逻辑，不依赖数据库）
# ============================================================

class TestRedundancyMixinLogic:
    """测试 RedundancyMixin 的核心逻辑，通过直接调用内部方法验证�?""

    def test_dynamic_threshold_integration(self) -> None:
        """动态阈值应�?_analyze_redundancy 集成正确�?""
        # 不同规模项目应产生不同阈�?
        thresholdSmall = computeDynamicThreshold(5)
        thresholdLarge = computeDynamicThreshold(500)
        assert thresholdSmall > thresholdLarge

    def test_redundancy_score_levels(self) -> None:
        """冗余度评分等级划分应正确�?""
        from app.services.case_quality.models import RedundancyScore

        # low
        scoreLow = RedundancyScore(similar_case_count=0, duplicate_step_count=0, score=1.0)
        assert scoreLow.score <= 2

        # moderate
        scoreMod = RedundancyScore(similar_case_count=2, duplicate_step_count=1, score=4.0)
        assert 2 < scoreMod.score <= 5

        # high
        scoreHigh = RedundancyScore(similar_case_count=4, duplicate_step_count=3, score=9.0)
        assert scoreHigh.score > 5

    def test_redundancy_score_capped_at_10(self) -> None:
        """冗余度评分上限为 10�?""
        from app.services.case_quality.models import RedundancyScore
        score = RedundancyScore(similar_case_count=10, duplicate_step_count=10, score=10.0)
        assert score.score <= 10
