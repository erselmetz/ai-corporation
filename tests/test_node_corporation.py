from app.node import Node, NodeRegistry
from app.corporation import Corporation, CorporationRegistry

def test_node_corporation_linkage():
    corp_registry = CorporationRegistry()
    node_registry = NodeRegistry(corporation_registry=corp_registry)
    
    corp = Corporation(id="corp_1", name="ERSELMETZ AI Corp")
    corp_registry.register(corp)
    
    # Valid registration
    node1 = Node(id="node_1", corporation_id="corp_1", name="Node 1")
    node_registry.register(node1)
    assert node_registry.exists("node_1")
    
    # Invalid registration (corp doesn't exist)
    node_invalid = Node(id="node_inv", corporation_id="corp_missing", name="Invalid Node")
    try:
        node_registry.register(node_invalid)
        raise AssertionError("Should have raised ValueError for missing corporation")
    except ValueError as e:
        assert "Corporation corp_missing does not exist" in str(e)

def test_find_nodes_by_corporation():
    corp_registry = CorporationRegistry()
    node_registry = NodeRegistry(corporation_registry=corp_registry)
    
    corp_id = "corp_1"
    corp = Corporation(id=corp_id, name="Corp 1")
    corp_registry.register(corp)
    
    node1 = Node(id="n1", corporation_id=corp_id, name="Node 1")
    node2 = Node(id="n2", corporation_id=corp_id, name="Node 2")
    node3 = Node(id="n3", corporation_id="corp_2", name="Node 3")
    
    node_registry.register(node1)
    node_registry.register(node2)
    # node3 registration would fail if we used the registry validation, but we can bypass if needed
    # however, to be consistent we only register valid ones.
    
    corp2 = Corporation(id="corp_2", name="Corp 2")
    corp_registry.register(corp2)
    node_registry.register(node3)
    
    nodes = node_registry.find_by_corporation(corp_id)
    assert len(nodes) == 2
    assert node1 in nodes
    assert node2 in nodes
    assert node3 not in nodes

def test_compatibility():
    # Ensure NodeRegistry still works without a corporation_registry (backward compat)
    node_registry = NodeRegistry()
    node = Node(id="node_1", corporation_id="any", name="Node 1")
    node_registry.register(node)
    assert node_registry.exists("node_1")

if __name__ == "__main__":
    try:
        test_node_corporation_linkage()
        test_find_nodes_by_corporation()
        test_compatibility()
        print("Node/Corporation relationship tests passed!")
    except Exception as e:
        print(f"Node/Corporation relationship tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
