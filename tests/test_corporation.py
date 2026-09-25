from app.corporation import Corporation, CorporationRegistry

def test_corporation_creation():
    corp = Corporation(id="corp_1", name="ERSELMETZ AI Corp")
    assert corp.id == "corp_1"
    assert corp.name == "ERSELMETZ AI Corp"

def test_corporation_validation():
    try:
        Corporation(id="", name="Name")
        raise AssertionError("Should have raised ValueError for empty id")
    except ValueError as e:
        assert "Corporation id cannot be empty" in str(e)

    try:
        Corporation(id="  ", name="Name")
        raise AssertionError("Should have raised ValueError for whitespace id")
    except ValueError as e:
        assert "Corporation id cannot be empty" in str(e)

    try:
        Corporation(id="id", name="")
        raise AssertionError("Should have raised ValueError for empty name")
    except ValueError as e:
        assert "Corporation name cannot be empty" in str(e)

    try:
        Corporation(id="id", name="  ")
        raise AssertionError("Should have raised ValueError for whitespace name")
    except ValueError as e:
        assert "Corporation name cannot be empty" in str(e)

def test_corporation_registry():
    registry = CorporationRegistry()
    corp = Corporation(id="corp_1", name="ERSELMETZ AI Corp")
    
    # Registration
    registry.register(corp)
    assert registry.exists("corp_1")
    assert registry.get("corp_1") == corp
    
    # Duplicate rejection
    try:
        registry.register(corp)
        raise AssertionError("Should have raised ValueError for duplicate registration")
    except ValueError as e:
        assert "Corporation already registered: corp_1" in str(e)
        
    # Missing lookup
    try:
        registry.get("missing")
        raise AssertionError("Should have raised ValueError for missing corp")
    except ValueError as e:
        assert "Corporation not found: missing" in str(e)
        
    # Listing
    corp2 = Corporation(id="corp_2", name="Other Corp")
    registry.register(corp2)
    assert len(registry.all()) == 2
    assert corp in registry.all()
    assert corp2 in registry.all()

if __name__ == "__main__":
    try:
        test_corporation_creation()
        test_corporation_validation()
        test_corporation_registry()
        print("Corporation identity tests passed!")
    except Exception as e:
        print(f"Corporation identity tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
