"""脚手架冒烟测试：验证包结构与依赖可导入。"""


def test_app_package_importable():
    import app
    assert app.__file__ is not None


def test_graph_package_importable():
    from app import graph, services, models, tools, utils
    assert graph and services and models and tools and utils


def test_langgraph_available():
    import langgraph
    assert langgraph is not None


def test_pydantic_available():
    from pydantic import BaseModel
    assert BaseModel is not None
