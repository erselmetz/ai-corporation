from app.runtime import RuntimeContext, RuntimeInitializer
from app.corporation import Corporation, CorporationRegistry
from app.node import Node, NodeRegistry

def test_runtime_initialization_success():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    corp = Corporation(id="corp_1", name="Corp 1")
    corp_reg.register(corp)
    
    node = Node(id="node_1", corporation_id="corp_1", name="Node 1")
    node_reg.register(node)
    
    context = RuntimeContext(corporation_id="corp_1", node_id="node_1")
    initializer = RuntimeInitializer(corp_reg, node_reg, context)
    
    validated_context = initializer.initialize()
    assert validated_context == context
    assert initializer.is_initialized is True

def test_runtime_initialization_invalid_corp():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    # Node exists but corp doesn't (in the registry)
    node = Node(id="node_1", corporation_id="corp_1", name="Node 1")
    node_reg.register(node)
    
    context = RuntimeContext(corporation_id="corp_1", node_id="node_1")
    initializer = RuntimeInitializer(corp_reg, node_reg, context)
    
    try:
        initializer.initialize()
        raise AssertionError("Should have failed due to missing corporation")
    except ValueError as e:
        assert "Corporation corp_1 not found" in str(e)
    assert initializer.is_initialized is False

def test_runtime_initialization_invalid_node():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    corp = Corporation(id="corp_1", name="Corp 1")
    corp_reg.register(corp)
    
    context = RuntimeContext(corporation_id="corp_1", node_id="node_missing")
    initializer = RuntimeInitializer(corp_reg, node_reg, context)
    
    try:
        initializer.initialize()
        raise AssertionError("Should have failed due to missing node")
    except ValueError as e:
        assert "Node node_missing not found" in str(e)
    assert initializer.is_initialized is False

def test_runtime_initialization_mismatch():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    corp1 = Corporation(id="corp_1", name="Corp 1")
    corp_reg.register(corp1)
    corp2 = Corporation(id="corp_2", name="Corp 2")
    corp_reg.register(corp2)
    
    node = Node(id="node_1", corporation_id="corp_1", name="Node 1")
    node_reg.register(node)
    
    # Context says node_1 is in corp_2
    context = RuntimeContext(corporation_id="corp_2", node_id="node_1")
    initializer = RuntimeInitializer(corp_reg, node_reg, context)
    
    try:
        initializer.initialize()
        raise AssertionError("Should have failed due to corp/node mismatch")
    except ValueError as e:
        assert "does not belong to Corporation corp_2" in str(e)
    assert initializer.is_initialized is False

def test_runtime_initialization_invalid_ids():
    corp_reg = CorporationRegistry()
    node_reg = NodeRegistry()
    
    # This should fail at the RuntimeContext construction level
    try:
        context = RuntimeContext(corporation_id=" ", node_id="node_1")
        initializer = RuntimeInitializer(corp_reg, node_reg, context)
        initializer.initialize()
    except ValueError as e:
        assert "Corporation id cannot be empty" in str(e)

if __name__ == "__main__":
    try:
        test_runtime_initialization_success()
        test_runtime_initialization_invalid_corp()
        test_runtime_initialization_invalid_node()
        test_runtime_initialization_mismatch()
        test_runtime_initialization_invalid_ids()
        print("Runtime initialization tests passed!")
    except Exception as e:
        print(f"Runtime initialization tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
