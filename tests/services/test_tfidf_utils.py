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


class TestTokenize:
    def test_english(self):
        tokens = tokenize("hello world")
        assert "hello" in tokens
        assert "world" in tokens

    def test_chinese_bigram(self):
        tokens = tokenize("用户登录")
        assert "用户" in tokens
        assert "户登" in tokens
        assert "登录" in tokens

    def test_mixed(self):
        tokens = tokenize("用户login系统")
        assert "login" in tokens
        assert "用户" in tokens

    def test_empty_string(self):
        assert tokenize("") == []

    def test_whitespace_only(self):
        assert tokenize("   ") == []

    def test_single_chinese_char(self):
        tokens = tokenize("中")
        assert "中" in tokens

    def test_numbers(self):
        tokens = tokenize("test123")
        assert "test123" in tokens


class TestLightweightTfidfVectorizer:
    def test_fit_transform_basic(self):
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["hello world", "hello python"])
        assert matrix.shape[0] == 2
        assert matrix.shape[1] > 0

    def test_fit_transform_empty(self):
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform([])
        assert matrix.shape == (0, 0)

    def test_fit_transform_single_doc(self):
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["hello world"])
        assert matrix.shape[0] == 1

    def test_fit_transform_empty_doc(self):
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["", "hello"])
        assert matrix.shape[0] == 2

    def test_transform_after_fit(self):
        vectorizer = LightweightTfidfVectorizer()
        vectorizer.fit_transform(["hello world", "hello python"])
        matrix = vectorizer.transform(["hello world"])
        assert matrix.shape[0] == 1

    def test_transform_without_fit_raises(self):
        vectorizer = LightweightTfidfVectorizer()
        with pytest.raises(RuntimeError, match="尚未拟合"):
            vectorizer.transform(["hello"])

    def test_l2_normalized(self):
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["hello world", "hello python"])
        norms = np.linalg.norm(matrix, axis=1)
        for norm in norms:
            if norm > 0:
                assert abs(norm - 1.0) < 1e-6

    def test_max_features(self):
        vectorizer = LightweightTfidfVectorizer(maxFeatures=2)
        docs = ["alpha beta gamma delta", "alpha beta gamma epsilon"]
        matrix = vectorizer.fit_transform(docs)
        assert matrix.shape[1] <= 2


class TestCosineSimilarity:
    def test_identical_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([1.0, 0.0])
        assert cosineSimilarity(a, b) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosineSimilarity(a, b) == pytest.approx(0.0)

    def test_empty_vectors(self):
        a = np.array([])
        b = np.array([])
        assert cosineSimilarity(a, b) == 0.0

    def test_zero_vectors(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 0.0])
        assert cosineSimilarity(a, b) == 0.0


class TestCosineSimilarityMatrix:
    def test_basic(self):
        vectorizer = LightweightTfidfVectorizer()
        matrix = vectorizer.fit_transform(["hello world", "hello python", "foo bar"])
        sim = cosineSimilarityMatrix(matrix)
        assert sim.shape == (3, 3)
        assert sim[0, 0] == pytest.approx(1.0)
        assert sim[0, 1] >= 0.0
        assert sim[0, 1] <= 1.0

    def test_empty_matrix(self):
        matrix = np.array([]).reshape(0, 0)
        sim = cosineSimilarityMatrix(matrix)
        assert sim.shape == (0, 0)


class TestComputeDynamicThreshold:
    def test_very_small_project(self):
        assert computeDynamicThreshold(5) == 0.85

    def test_small_project(self):
        threshold = computeDynamicThreshold(20)
        assert 0.78 <= threshold <= 0.85

    def test_medium_project(self):
        threshold = computeDynamicThreshold(50)
        assert 0.70 <= threshold <= 0.78

    def test_large_project(self):
        threshold = computeDynamicThreshold(200)
        assert 0.62 <= threshold <= 0.70

    def test_very_large_project(self):
        threshold = computeDynamicThreshold(500)
        assert threshold >= 0.55

    def test_zero_cases(self):
        assert computeDynamicThreshold(0) == 0.85

    def test_boundary_10(self):
        threshold = computeDynamicThreshold(10)
        assert threshold == 0.85

    def test_boundary_30(self):
        threshold = computeDynamicThreshold(30)
        assert threshold == pytest.approx(0.78)


class TestBatchComputeSimilarity:
    def test_basic(self):
        sim = batchComputeSimilarity(
            ["用户登录系统"], ["用户登录页面", "数据导出功能"],
        )
        assert sim.shape == (1, 2)
        assert sim[0, 0] >= sim[0, 1]

    def test_empty_targets(self):
        sim = batchComputeSimilarity([], ["hello"])
        assert sim.shape == (0, 1)

    def test_empty_candidates(self):
        sim = batchComputeSimilarity(["hello"], [])
        assert sim.shape == (1, 0)

    def test_both_empty(self):
        sim = batchComputeSimilarity([], [])
        assert sim.shape == (0, 0)
