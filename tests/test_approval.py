from app.approval import ApprovalRequest, ApprovalStatus, ApprovalRegistry

def test_approval_creation():
    request = ApprovalRequest(
        id="req_1",
        action="delete_file",
        context="Deleting temporary file /tmp/test.txt"
    )
    assert request.id == "req_1"
    assert request.action == "delete_file"
    assert request.status == ApprovalStatus.PENDING

def test_approval_validation():
    # Simple verification without pytest for the minimal runner
    try:
        ApprovalRequest(id="", action="action", context="context")
        raise AssertionError("Should have raised ValueError for empty id")
    except ValueError as e:
        assert "Approval request id cannot be empty" in str(e)

    try:
        ApprovalRequest(id="id", action="", context="context")
        raise AssertionError("Should have raised ValueError for empty action")
    except ValueError as e:
        assert "Action cannot be empty" in str(e)

    try:
        ApprovalRequest(id="id", action="action", context="")
        raise AssertionError("Should have raised ValueError for empty context")
    except ValueError as e:
        assert "Context cannot be empty" in str(e)

def test_approval_registry_basic():
    registry = ApprovalRegistry()
    request = ApprovalRequest(id="req_1", action="action", context="context")
    
    registry.register(request)
    assert registry.exists("req_1")
    assert registry.get("req_1") == request
    assert len(registry.all()) == 1

def test_approval_duplicate_registration():
    registry = ApprovalRegistry()
    request = ApprovalRequest(id="req_1", action="action", context="context")
    registry.register(request)
    
    try:
        registry.register(request)
        raise AssertionError("Should have raised ValueError for duplicate registration")
    except ValueError as e:
        assert "Approval request already registered: req_1" in str(e)

def test_approval_workflow():
    registry = ApprovalRegistry()
    request = ApprovalRequest(id="req_1", action="action", context="context")
    registry.register(request)
    
    # Test approval
    registry.approve("req_1")
    assert request.status == ApprovalStatus.APPROVED
    
    # Test invalid transition from approved to rejected
    try:
        registry.reject("req_1")
        raise AssertionError("Should have raised RuntimeError for invalid transition from approved to rejected")
    except RuntimeError as e:
        assert "Must be pending" in str(e)

def test_approval_rejection_workflow():
    registry = ApprovalRegistry()
    request = ApprovalRequest(id="req_2", action="action", context="context")
    registry.register(request)
    
    # Test rejection
    registry.reject("req_2")
    assert request.status == ApprovalStatus.REJECTED
    
    # Test invalid transition from rejected to approved
    try:
        registry.approve("req_2")
        raise AssertionError("Should have raised RuntimeError for invalid transition from rejected to approved")
    except RuntimeError as e:
        assert "Must be pending" in str(e)

if __name__ == "__main__":
    try:
        test_approval_creation()
        test_approval_validation()
        test_approval_registry_basic()
        test_approval_duplicate_registration()
        test_approval_workflow()
        test_approval_rejection_workflow()
        print("Approval system tests passed!")
    except Exception as e:
        print(f"Approval system tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
