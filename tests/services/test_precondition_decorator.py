import pytest
from app.services.precondition.decorator import handle_precondition_errors
from app.services.precondition.models import PreconditionError, PreconditionConfigError


class TestHandlePreconditionErrors:
    @pytest.mark.asyncio
    async def test_precondition_error_passes_through(self):
        @handle_precondition_errors
        async def failing_func():
            raise PreconditionConfigError("配置错误")

        with pytest.raises(PreconditionConfigError, match="配置错误"):
            await failing_func()

    @pytest.mark.asyncio
    async def test_generic_exception_converted(self):
        @handle_precondition_errors
        async def generic_fail():
            raise ValueError("未知错误")

        with pytest.raises(PreconditionError, match="失败"):
            await generic_fail()

    @pytest.mark.asyncio
    async def test_success_returns_value(self):
        @handle_precondition_errors
        async def success_func():
            return "ok"

        result = await success_func()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @handle_precondition_errors
        async def my_function():
            pass

        assert my_function.__name__ == "my_function"
