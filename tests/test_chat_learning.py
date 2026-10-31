from app.knowledge.chat_learning import retention_candidate


def test_chat_learning_accepts_explicit_owner_facts_and_preferences():
    assert retention_candidate('Remember that my preferred editor is VS Code') == 'Remember that my preferred editor is VS Code'
    assert retention_candidate('Gusto ko dark mode sa lahat ng page') == 'Gusto ko dark mode sa lahat ng page'


def test_chat_learning_rejects_chatter_questions_and_likely_secrets():
    assert retention_candidate('hello') is None
    assert retention_candidate('What should I use?') is None
    assert retention_candidate('Remember that api_key=super-secret-value') is None
