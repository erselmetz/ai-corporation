from app.node import Node, NodeRegistry
from app.corporation import Corporation, CorporationRegistry

def test_node_creation():
    node = Node(id="node_1", corporation_id="corp_1", name="Local Node")
    assert node.id == "node_1"
    assert node.corporation_id == "corp_1"
    assert node.name == "Local Node"

def test_node_validation():
    try:
        Node(id="", corporation_id="c1", name="N1")
        raise AssertionError("Should have raised ValueError for empty id")
    except ValueError as e:
        assert "Node id cannot be empty" in str(e)

    try:
        Node(id="n1", corporation_id=" ", name="N1")
        raise AssertionError("Should have raised ValueError for whitespace corp_id")
    except ValueError as e:
        assert "Corporation id cannot be empty" in str(e)

    try:
        Node(id="n1", corporation_id="c1", name="")
        raise AssertionError("Should have raised ValueError for empty name")
    except ValueError as e:
        assert "Node name cannot be empty" in str(e)

def test_node_registry():
    registry = NodeRegistry()
    node = Node(id="node_1", corporation_id="corp_1", name="Local Node")
    
    # Registration
    registry.register(node)
    assert registry.exists("node_1")
    assert registry.get("node_1") == node
    
    # Duplicate rejection
    try:
        registry.register(node)
        raise AssertionError("Should have raised ValueError for duplicate registration")
    except ValueError as e:
        assert "Node already registered: node_1" in str(e)
        
    # Missing lookup
    try:
        registry.get("missing")
        raise AssertionError("Should have raised ValueError for missing node")
    except ValueError as e:
        assert "Node not found: missing" in str(e)
        
    # Listing
    node2 = Node(id="node_2", corporation_id="corp_1", name="Cloud Node")
    registry.register(node2)
    assert len(registry.all()) == 2
    assert node in registry.all()
    assert node2 in registry.all()

def test_node_corporation_relationship():
    # Verify multiple nodes can belong to the same corporation
    corp_id = "corp_shared"
    node1 = Node(id="n1", corporation_id=corp_id, name="Node 1")
    node2 = Node(id="n2", corporation_id=corp_id, name="Node 2")
    
    assert node1.corporation_id == node2.corporation_id == corp_id

if __name__ == "__main__":
    try:
        test_node_creation()
        test_node_validation()
        test_node_registry()
        test_node_corporation_relationship()
        print("Node identity tests passed!")
    except Exception as e:
        print(f"Node identity tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
