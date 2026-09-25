from app.tools import Tool, ToolRegistry

class MockTool(Tool):
    """A simple mock tool for testing purposes."""
    def execute(self, **kwargs) -> str:
        return f"Mock tool executed with args: {kwargs}"

def test_tool_creation():
    tool = MockTool("test_tool", "Test Tool", "A tool that does nothing")
    assert tool.id == "test_tool"
    assert tool.name == "Test Tool"
    assert tool.description == "A tool that does nothing"
    assert tool.execute(param="value") == "Mock tool executed with args: {'param': 'value'}"

def test_tool_validation():
    # Simple verification without pytest for the minimal runner
    try:
        MockTool("", "Name", "Desc")
        raise AssertionError("Should have raised ValueError for empty id")
    except ValueError as e:
        assert "Tool id cannot be empty" in str(e)

    try:
        MockTool("id", " ", "Desc")
        raise AssertionError("Should have raised ValueError for empty name")
    except ValueError as e:
        assert "Tool name cannot be empty" in str(e)

    try:
        MockTool("id", "Name", "")
        raise AssertionError("Should have raised ValueError for empty description")
    except ValueError as e:
        assert "Tool description cannot be empty" in str(e)

def test_tool_registry():
    registry = ToolRegistry()
    tool = MockTool("t1", "Tool 1", "Desc 1")
    
    # Registration
    registry.register(tool)
    assert registry.exists("t1")
    assert registry.get("t1") == tool
    
    # Duplicate registration
    try:
        registry.register(tool)
        raise AssertionError("Should have raised ValueError for duplicate registration")
    except ValueError as e:
        assert "Tool already registered: t1" in str(e)
    
    # Lookup missing
    try:
        registry.get("missing")
        raise AssertionError("Should have raised ValueError for missing tool")
    except ValueError as e:
        assert "Tool not found: missing" in str(e)
        
    # Listing
    tool2 = MockTool("t2", "Tool 2", "Desc 2")
    registry.register(tool2)
    assert len(registry.all()) == 2
    assert tool in registry.all()
    assert tool2 in registry.all()

if __name__ == "__main__":
    try:
        test_tool_creation()
        test_tool_validation()
        test_tool_registry()
        print("Tool system tests passed!")
    except Exception as e:
        print(f"Tool system tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
