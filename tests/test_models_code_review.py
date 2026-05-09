import pytest
from datetime import datetime
from app.models.code_review import CodeReview, ReviewItem, ReviewComment, ReviewMetric
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="cr_test_user",
        email="cr_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(ReviewComment).filter(ReviewComment.user_id == user.id).delete(synchronize_session=False)
    db.query(ReviewMetric).filter(ReviewMetric.review_id.in_(
        db.query(CodeReview.id).filter(
            (CodeReview.reviewer_id == user.id) | (CodeReview.author_id == user.id)
        )
    )).delete(synchronize_session=False)
    db.query(ReviewItem).filter(ReviewItem.review_id.in_(
        db.query(CodeReview.id).filter(
            (CodeReview.reviewer_id == user.id) | (CodeReview.author_id == user.id)
        )
    )).delete(synchronize_session=False)
    db.query(CodeReview).filter(
        (CodeReview.reviewer_id == user.id) | (CodeReview.author_id == user.id)
    ).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def second_user(db):
    user = User(
        username="cr_second_user",
        email="cr_second@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()


class TestCodeReviewModel:
    def test_create_code_review(self, db, test_user, second_user):
        cr = CodeReview(
            title="代码审查1",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        assert cr.id is not None
        assert cr.title == "代码审查1"
        assert cr.repository == "https://github.com/test/repo"
        assert cr.branch == "main"
        assert cr.reviewer_id == test_user.id
        assert cr.author_id == second_user.id
        assert cr.status == "pending"
        assert cr.created_at is not None
        db.delete(cr)
        db.commit()

    def test_code_review_default_values(self, db, test_user, second_user):
        cr = CodeReview(
            title="默认值审�?,
            repository="https://github.com/test/repo",
            branch="dev",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        assert cr.status == "pending"
        assert cr.description is None
        assert cr.commit_id is None
        assert cr.review_type is None
        assert cr.completed_at is None
        db.delete(cr)
        db.commit()

    def test_code_review_status_values(self, db, test_user, second_user):
        for status in ["pending", "in_progress", "completed", "cancelled"]:
            cr = CodeReview(
                title=f"状态{status}",
                repository="https://github.com/test/repo",
                branch="main",
                reviewer_id=test_user.id,
                author_id=second_user.id,
                status=status
            )
            db.add(cr)
            db.commit()
            db.refresh(cr)
            assert cr.status == status
            db.delete(cr)
            db.commit()

    def test_code_review_type_values(self, db, test_user, second_user):
        for rtype in ["full", "quick", "security"]:
            cr = CodeReview(
                title=f"类型{rtype}",
                repository="https://github.com/test/repo",
                branch="main",
                reviewer_id=test_user.id,
                author_id=second_user.id,
                review_type=rtype
            )
            db.add(cr)
            db.commit()
            db.refresh(cr)
            assert cr.review_type == rtype
            db.delete(cr)
            db.commit()

    def test_code_review_with_commit(self, db, test_user, second_user):
        cr = CodeReview(
            title="带commit审查",
            repository="https://github.com/test/repo",
            branch="feature",
            commit_id="abc123def456",
            reviewer_id=test_user.id,
            author_id=second_user.id,
            completed_at=datetime(2024, 6, 1)
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        assert cr.commit_id == "abc123def456"
        assert cr.completed_at == datetime(2024, 6, 1)
        db.delete(cr)
        db.commit()

    def test_code_review_repr(self, db, test_user, second_user):
        cr = CodeReview(
            title="Repr测试",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        repr_str = repr(cr)
        assert "CodeReview" in repr_str
        db.delete(cr)
        db.commit()


class TestReviewItemModel:
    def test_create_review_item(self, db, test_user, second_user):
        cr = CodeReview(
            title="项目审查",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        item = ReviewItem(
            review_id=cr.id,
            file_path="src/main.py",
            line_start=10,
            line_end=20,
            issue_type="bug",
            description="空指针风�?
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.id is not None
        assert item.review_id == cr.id
        assert item.file_path == "src/main.py"
        assert item.line_start == 10
        assert item.line_end == 20
        assert item.issue_type == "bug"
        assert item.description == "空指针风�?
        assert item.status == "open"
        db.delete(item)
        db.delete(cr)
        db.commit()

    def test_review_item_default_values(self, db, test_user, second_user):
        cr = CodeReview(
            title="默认项审�?,
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        item = ReviewItem(
            review_id=cr.id,
            file_path="src/util.py",
            line_start=1,
            line_end=5,
            issue_type="style",
            description="格式问题"
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.severity is None
        assert item.recommendation is None
        assert item.status == "open"
        db.delete(item)
        db.delete(cr)
        db.commit()

    def test_review_item_severity_values(self, db, test_user, second_user):
        cr = CodeReview(
            title="严重度审�?,
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        for sev in ["critical", "major", "minor", "suggestion"]:
            item = ReviewItem(
                review_id=cr.id,
                file_path="src/app.py",
                line_start=1,
                line_end=2,
                issue_type="bug",
                description="问题",
                severity=sev
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            assert item.severity == sev
            db.delete(item)
            db.commit()
        db.delete(cr)
        db.commit()

    def test_review_item_status_values(self, db, test_user, second_user):
        cr = CodeReview(
            title="状态审�?,
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        for status in ["open", "acknowledged", "fixed", "wontfix"]:
            item = ReviewItem(
                review_id=cr.id,
                file_path="src/app.py",
                line_start=1,
                line_end=2,
                issue_type="bug",
                description="问题",
                status=status
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            assert item.status == status
            db.delete(item)
            db.commit()
        db.delete(cr)
        db.commit()


class TestReviewCommentModel:
    def test_create_review_comment(self, db, test_user, second_user):
        cr = CodeReview(
            title="评论审查",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        comment = ReviewComment(
            review_id=cr.id,
            user_id=test_user.id,
            content="这段代码需要优�?
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)
        assert comment.id is not None
        assert comment.review_id == cr.id
        assert comment.user_id == test_user.id
        assert comment.content == "这段代码需要优�?
        assert comment.created_at is not None
        db.delete(comment)
        db.delete(cr)
        db.commit()

    def test_review_comment_nullable_item(self, db, test_user, second_user):
        cr = CodeReview(
            title="评论项审�?,
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        comment = ReviewComment(
            review_id=cr.id,
            user_id=test_user.id,
            content="总体评价"
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)
        assert comment.review_item_id is None
        db.delete(comment)
        db.delete(cr)
        db.commit()


class TestReviewMetricModel:
    def test_create_review_metric(self, db, test_user, second_user):
        cr = CodeReview(
            title="指标审查",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        metric = ReviewMetric(
            review_id=cr.id,
            metric_name="total_issues",
            metric_value="5"
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)
        assert metric.id is not None
        assert metric.review_id == cr.id
        assert metric.metric_name == "total_issues"
        assert metric.metric_value == "5"
        assert metric.created_at is not None
        db.delete(metric)
        db.delete(cr)
        db.commit()

    def test_review_metric_types(self, db, test_user, second_user):
        cr = CodeReview(
            title="多指标审�?,
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=test_user.id,
            author_id=second_user.id
        )
        db.add(cr)
        db.commit()
        db.refresh(cr)
        for name in ["total_issues", "coverage_score", "complexity_avg"]:
            metric = ReviewMetric(
                review_id=cr.id,
                metric_name=name,
                metric_value="10"
            )
            db.add(metric)
            db.commit()
            db.refresh(metric)
            assert metric.metric_name == name
            db.delete(metric)
            db.commit()
        db.delete(cr)
        db.commit()
