from pathlib import Path

from streamlit.testing.v1 import AppTest

_HARNESS = str(Path(__file__).parent / "apps" / "harness_professional.py")


def test_create_session_shows_visible_code():
    at = AppTest.from_file(_HARNESS)
    at.run()
    assert not at.exception

    create_tab = at.tabs[0]
    create_tab.radio[0].set_value("Primera consulta")
    create_tab.text_area[0].set_value("Dolor lumbar de 3 semanas")
    create_tab.button[0].click().run()

    assert not at.exception
    assert "Sesión creada" in "".join(m.value for m in at.success)
    codes = [m.value for m in at.tabs[0].metric]
    assert len(codes) == 1
    assert len(codes[0]) == 6


def test_looking_up_nonexistent_session_shows_error():
    at = AppTest.from_file(_HARNESS)
    at.run()

    lookup_tab = at.tabs[1]
    lookup_tab.text_input[0].set_value("NOEXISTE").run()

    assert not at.exception
    assert any("No existe ninguna sesión" in e.value for e in at.error)


def test_create_then_look_up_same_session():
    at = AppTest.from_file(_HARNESS)
    at.run()

    at.tabs[0].radio[0].set_value("Seguimiento")
    at.tabs[0].button[0].click().run()
    code = at.tabs[0].metric[0].value

    at.tabs[1].text_input[0].set_value(code).run()

    assert not at.exception
    texts = [w.value for w in at.tabs[1].markdown]
    assert any("Seguimiento" in t for t in texts)
    assert any("Creada" in t for t in texts)


def test_new_session_defaults_to_nutrition_specialty():
    at = AppTest.from_file(_HARNESS)
    at.run()

    at.tabs[0].radio[0].set_value("Primera consulta")
    at.tabs[0].button[0].click().run()
    code = at.tabs[0].metric[0].value

    at.tabs[1].text_input[0].set_value(code).run()

    assert not at.exception
    texts = [w.value for w in at.tabs[1].markdown]
    assert any("Nutrición" in t for t in texts)


def test_specialty_can_be_overridden():
    at = AppTest.from_file(_HARNESS)
    at.run()

    at.tabs[0].radio[0].set_value("Primera consulta")
    at.tabs[0].text_input[0].set_value("Fisioterapia")
    at.tabs[0].button[0].click().run()
    code = at.tabs[0].metric[0].value

    at.tabs[1].text_input[0].set_value(code).run()

    assert not at.exception
    texts = [w.value for w in at.tabs[1].markdown]
    assert any("Fisioterapia" in t for t in texts)
