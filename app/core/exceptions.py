class AppError(Exception):
    def __init__(self, status_code: int, code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class ContentRejectedError(AppError):
    def __init__(self) -> None:
        super().__init__(422, 4003, "内容暂不支持，请调整主题后重试。")


class AIConfigurationError(AppError):
    def __init__(self) -> None:
        super().__init__(503, 5002, "AI 服务尚未配置，请联系服务维护者。")


class QuizGenerationError(AppError):
    def __init__(self) -> None:
        super().__init__(502, 5001, "题目生成失败，请稍后重试。")


class ReportGenerationError(AppError):
    def __init__(self) -> None:
        super().__init__(502, 5003, "复盘报告生成失败，请稍后重试。")


class AuthenticationRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(401, 4010, "请先完成微信登录。")


class WechatLoginError(AppError):
    def __init__(self) -> None:
        super().__init__(401, 4011, "微信登录失败，请重试。")


class WechatConfigurationError(AppError):
    def __init__(self) -> None:
        super().__init__(503, 5004, "微信登录尚未配置，请联系服务维护者。")


class DatabaseConfigurationError(AppError):
    def __init__(self) -> None:
        super().__init__(503, 5005, "数据库尚未配置，请联系服务维护者。")


class UserNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__(404, 4004, "用户或学习记录不存在。")
