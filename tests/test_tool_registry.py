import logging

logger = logging.getLogger(__name__)

def test_read_file_tool_registry():
    from agent.tools.tool_manager import registry
    _modules = [
        "agent.tools.file_tool"
    ]
    import importlib
    for mod_name in _modules:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            logger.warning("Could not import tool module %s: %s", mod_name, e)

    assert "read_file" in registry.available()

