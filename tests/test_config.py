"""T0.2 验收：Config 默认值与需求文档一致。"""
from app.config import Config


def test_sign_day_tiers():
    c = Config()
    assert c.SIGN_DAY_TIER1 == 7
    assert c.SIGN_DAY_TIER2 == 15


def test_amount_threshold():
    assert Config().AMOUNT_THRESHOLD == 2000.0


def test_ask_max_rounds():
    c = Config()
    assert c.ASK_ORDER_MAX == 2
    assert c.ASK_IDENTITY_MAX == 2
    assert c.ASK_CONFIRM_MAX == 3
    assert c.WRITE_REFUND_RETRY == 2


def test_context_window_and_timeout():
    c = Config()
    assert c.CONTEXT_WINDOW == 5
    assert c.SESSION_TIMEOUT == 1800


def test_max_orders():
    assert Config().MAX_ORDERS == 5


def test_soothe_max():
    assert Config().SOOTHE_MAX_PER_SESSION == 2


def test_instance_override():
    c = Config()
    c.AMOUNT_THRESHOLD = 500.0
    assert c.AMOUNT_THRESHOLD == 500.0
    # 默认实例不受影响
    assert Config().AMOUNT_THRESHOLD == 2000.0
