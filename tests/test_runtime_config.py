from app.runtime import RuntimeConfig, RuntimeContext
from app.corporation import Corporation, CorporationRegistry
from app.node import Node, NodeRegistry
from app.runtime import RuntimeInitializer

def test_config_creation():
    config = RuntimeConfig(corporation_id="corp_1", node_id="node_1")
    assert config.corporation_id == "corp_1"
    assert config.node_id == "node_1"

def test_config_validation():
    try:
        RuntimeConfig(corporation_id="", node_id="node_1")
        raise AssertionError("Should have raised ValueError for empty corp_id")
    except ValueError as e:
        assert "Configuration: corporation_id cannot be empty" in str(e)

    try:
        RuntimeConfig(corporation_id="  ", node_id="node_1")
        raise AssertionError("Should have raised ValueError for whitespace corp_id")
    except ValueError as e:
        assert "Configuration: corporation_id cannot be empty" in str(e)

    try:
        RuntimeConfig(corporation_id="corp_1", node_id="")
        raise AssertionError("Should have raised ValueError for empty node_id")
    except ValueError as e:
        assert "Configuration: node_id cannot be empty" in str(e)

    try:
        RuntimeConfig(corporation_id="corp_1", node_id=" ")
        raise AssertionError("Should have raised ValueError for whitespace node_id")
    except ValueError as e:
        assert "Configuration: node_id cannot be empty" in str(e)

def test_config_to_context():
    config = RuntimeConfig(corporation_id="corp_1", node_id="node_1")
    context = config.to_context()
    assert context.corporation_id == config.corporation_id
    assert context.node_id == config.node_id

if __name__ == "__main__":
    try:
        test_config_creation()
        test_config_validation()
        test_config_to_context()
        print("Runtime configuration tests passed!")
    except Exception as e:
        print(f"Runtime configuration tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
