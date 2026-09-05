from jobbot.personas import PERSONAS, assign_persona, get_persona


def test_persona_keys_are_unique():
    keys = [p.key for p in PERSONAS]
    assert len(keys) == len(set(keys))


def test_assign_persona_returns_one_of_the_defined_variants():
    for _ in range(20):
        assert assign_persona() in PERSONAS


def test_get_persona_looks_up_by_key():
    for persona in PERSONAS:
        assert get_persona(persona.key) is persona


def test_get_persona_falls_back_for_unknown_or_empty_key():
    assert get_persona("") is PERSONAS[0]
    assert get_persona("not-a-real-persona") is PERSONAS[0]
