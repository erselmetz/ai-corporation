from app.runtime import RuntimeContext, RuntimeContextManager
from app.corporation import Corporation, CorporationRegistry
from app.node import Node, NodeRegistry

def test_runtime_context_creation():
    context = RuntimeContext(corporation_id="corp_1", node_id="node_1")
    assert context.corporation_id == "corp_1"
    assert context.node_id == "node_1"

def test_runtime_context_validation():
    try:
        RuntimeContext(corporation_id="", node_id="node_1")
        raise AssertionError("Should have raised ValueError for empty corp_id")
    except ValueError as e:
        assert "Corporation id cannot be empty" in str(e)

    try:
        RuntimeContext(corporation_id="corp_1", node_id=" ")
        raise AssertionError("Should have raised ValueError for whitespace node_id")
    except ValueError as e:
        assert "Node id cannot be empty" in str(e)

def test_runtime_context_validation_success():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    corp = Corporation(id="corp_1", name="Corp 1")
    corp_reg.register(corp)
    
    node = Node(id="node_1", corporation_id="corp_1", name="Node 1")
    node_reg.register(node)
    
    manager = RuntimeContextManager(corp_reg, node_reg)
    context = RuntimeContext(corporation_id="corp_1", node_id="node_1")
    
    assert manager.validate_context(context) is True

def test_runtime_context_invalid_corporation():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    node = Node(id="node_1", corporation_id="corp_1", name="Node 1")
    node_reg.register(node)
    
    manager = RuntimeContextManager(corp_reg, node_reg)
    context = RuntimeContext(corporation_id="corp_1", node_id="node_1")
    
    try:
        manager.validate_context(context)
        raise AssertionError("Should have raised ValueError for non-existent corporation")
    except ValueError as e:
        assert "Corporation corp_1 not found" in str(e)

def test_runtime_context_invalid_node():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    corp = Corporation(id="corp_1", name="Corp 1")
    corp_reg.register(corp)
    
    manager = RuntimeContextManager(corp_reg, node_reg)
    context = RuntimeContext(corporation_id="corp_1", node_id="node_missing")
    
    try:
        manager.validate_context(context)
        raise AssertionError("Should have raised ValueError for non-existent node")
    except ValueError as e:
        assert "Node node_missing not found" in str(e)

def test_runtime_context_mismatched_corporation():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    corp1 = Corporation(id="corp_1", name="Corp 1")
    corp_reg.register(corp1)
    corp2 = Corporation(id="corp_2", name="Corp 2")
    corp_reg.register(corp2)
    
    node = Node(id="node_1", corporation_id="corp_1", name="Node 1")
    node_reg.register(node)
    
    manager = RuntimeContextManager(corp_reg, node_reg)
    # Node belongs to corp_1, but context says corp_2
    context = RuntimeContext(corporation_id="corp_2", node_id="node_1")
    
    try:
        manager.validate_context(context)
        raise AssertionError("Should have raised ValueError for mismatched corporation")
    except ValueError as e:
        assert "does not belong to Corporation corp_2" in str(e)

if __name__ == "__main__":
    try:
        test_runtime_context_creation()
        test_runtime_context_validation()
        test_runtime_context_validation_success()
        test_runtime_context_invalid_corporation()
        test_runtime_context_invalid_node()
        test_runtime_context_mismatched_corporation()
        print("Runtime context tests passed!")
    except Exception as e:
        print(f"Runtime context tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
