import pytest
from app.services.precondition.utils import solve_captcha_math, recognize_login_form
from app.services.precondition.models import PreconditionError, LoginFormInfo


class TestSolveCaptchaMath:
    def test_addition_chinese(self):
        assert solve_captcha_math("3＋5=??") == "8"

    def test_subtraction_chinese(self):
        assert solve_captcha_math("10－3=?") == "7"

    def test_multiplication_chinese(self):
        assert solve_captcha_math("4×6=?") == "24"

    def test_division_chinese(self):
        assert solve_captcha_math("10÷2=?") == "5"

    def test_addition_ascii(self):
        assert solve_captcha_math("3 + 5 = ?") == "8"

    def test_subtraction_ascii(self):
        assert solve_captcha_math("10 - 3 = ?") == "7"

    def test_multiplication_ascii(self):
        assert solve_captcha_math("4 * 6 = ?") == "24"

    def test_division_ascii(self):
        assert solve_captcha_math("10 / 2 = ?") == "5"

    def test_division_by_zero(self):
        result = solve_captcha_math("10 / 0 = ?")
        assert isinstance(result, str)

    def test_single_number(self):
        assert solve_captcha_math("42") == "42"

    def test_multiple_numbers_returns_short(self):
        result = solve_captcha_math("abc 123 4567")
        assert result in ("123", "4567")

    def test_alphanumeric_fallback(self):
        result = solve_captcha_math("code ABC123")
        assert result in ("ABC123", "123")

    def test_captcha_keyword_filtered(self):
        result = solve_captcha_math("captcha ABC123")
        assert result in ("ABC123", "123")

    def test_empty_string(self):
        assert solve_captcha_math("") == ""

    def test_short_cleaned_text(self):
        result = solve_captcha_math("result: 42")
        assert result == "42"

    def test_long_text_fallback(self):
        result = solve_captcha_math("this is a very long text that exceeds ten characters")
        assert isinstance(result, str)

    def test_math_expression_without_equals(self):
        assert solve_captcha_math("3+5") == "8"


class TestRecognizeLoginForm:
    def test_no_vision_model_raises(self):
        with pytest.raises(PreconditionError, match="视觉模型未初始化"):
            recognize_login_form(None, b"fake_screenshot")

    def test_valid_json_response(self):
        vision_model = type("VM", (), {})()
        vision_model.analyze_image = lambda screenshot, prompt: '''
        {
            "username_input": {"x": 100, "y": 200, "width": 200, "height": 30},
            "password_input": {"x": 100, "y": 250, "width": 200, "height": 30},
            "submit_button": {"x": 150, "y": 320, "width": 100, "height": 40}
        }
        '''
        result = recognize_login_form(vision_model, b"screenshot")
        assert isinstance(result, LoginFormInfo)
        assert result.username_input is not None
        assert result.password_input is not None
        assert result.submit_button is not None

    def test_no_json_in_response(self):
        vision_model = type("VM", (), {})()
        vision_model.analyze_image = lambda screenshot, prompt: "no json here"
        result = recognize_login_form(vision_model, b"screenshot")
        assert isinstance(result, LoginFormInfo)
        assert result.username_input is None

    def test_invalid_json_response(self):
        vision_model = type("VM", (), {})()
        vision_model.analyze_image = lambda screenshot, prompt: "{invalid json}"
        result = recognize_login_form(vision_model, b"screenshot")
        assert isinstance(result, LoginFormInfo)

    def test_exception_in_vision_model(self):
        vision_model = type("VM", (), {})()
        vision_model.analyze_image = lambda screenshot, prompt: (_ for _ in ()).throw(RuntimeError("fail"))
        result = recognize_login_form(vision_model, b"screenshot")
        assert isinstance(result, LoginFormInfo)

    def test_captcha_fields_parsed(self):
        vision_model = type("VM", (), {})()
        vision_model.analyze_image = lambda screenshot, prompt: '''
        {
            "username_input": {"x": 100, "y": 200},
            "password_input": {"x": 100, "y": 250},
            "submit_button": {"x": 150, "y": 320},
            "captcha_input": {"x": 100, "y": 380},
            "captcha_image": {"x": 260, "y": 380}
        }
        '''
        result = recognize_login_form(vision_model, b"screenshot")
        assert result.captcha_input is not None
        assert result.captcha_image is not None
