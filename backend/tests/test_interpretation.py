import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from homechem.interpretation import resolve
from homechem.main import app
from homechem.policy import Surface


@pytest.mark.parametrize(("text", "surface", "materials", "term"), [
    ("Can I clean dust off my GLASS-TABLE?", "glass_tabletop", "not_stated", "glass_tabletop"),
    ("How do I clean my ceramic sink?", "ceramic_sink", "not_stated", "ceramic_sink"),
    ("How do I clean my glass screen with a dry microfiber cloth?",
     "glass_screen", "dry_microfiber_only", "glass_screen"),
    ("Clean my porcelain sink with warm water, mild dish soap, and a soft cloth",
     "ceramic_sink", "mild_dish_soap_water_and_soft_cloth", "ceramic_sink"),
    ("Wiping a fireclay basin with water, mild dish soap, and a soft cleaning cloth",
     "ceramic_sink", "mild_dish_soap_water_and_soft_cloth", "ceramic_sink"),
    ("I want to clean my stainless-steel sink", "unknown", "not_stated", "stainless_steel_sink"),
    ("Cleaning the windows", "unknown", "not_stated", "window"),
    ("Clean the glass table and the ceramic sink", "unknown", "not_stated", None),
    ("Clean my coated glass table", "unknown", "not_stated", "tabletop"),
    ("Clean the glass table with water, a microfiber cloth, and PurpleMagic",
     "glass_tabletop", "unknown", "glass_tabletop"),
    ("Clean glass table with water and microfiber cloth, without bleach",
     "glass_tabletop", "unknown", "glass_tabletop"),
    ("Clean the glass table with water", "glass_tabletop", "unknown", "glass_tabletop"),
])
def test_lexicon_resolution(text, surface, materials, term):
    result = resolve(text)
    assert result.interpretation.surface == surface
    assert result.interpretation.materials == materials
    assert result.surface_term == term
    assert not result.allow_model


@pytest.mark.parametrize(("text", "object_type"), [
    ("Clean a teaspoon with Nutella on it", "cutlery"),
    ("Clean my stainless steel forks", "cutlery"),
    ("Clean my butter knives", "cutlery"),
    ("I clean a dirty spoonful of Nutella.", None),
])
def test_cutlery_category_uses_wordnet_object_senses(text, object_type):
    result = resolve(text)
    assert result.object_type == object_type
    assert result.interpretation.surface == Surface.UNKNOWN
    if object_type is not None:
        assert not result.allow_model


@pytest.mark.parametrize(("text", "object_type", "substrate", "finish", "surface", "materials"), [
    ("I want to clean my ceramic floor", "floor", "ceramic", None, "ceramic_tile_floor", "not_stated"),
    ("Clean my glazed porcelain tile floor with water and a microfiber mop",
     "floor", "ceramic", "glazed", "ceramic_tile_floor", "water_and_mop_only"),
    ("Wiping glazed ceramic floor tiles with water and a mop",
     "floor", "ceramic", "glazed", "ceramic_tile_floor", "water_and_mop_only"),
    ("Clean the unglazed ceramic floor", "floor", "ceramic", "unglazed", "unknown", "not_stated"),
    ("Clean a ceramic sink with glass cleaner", "sink", "ceramic", None, "ceramic_sink", "unknown"),
    ("Clean my ceramic", None, "ceramic", None, "unknown", "not_stated"),
    ("Clean ceramic on my floor", "floor", "ceramic", None, "unknown", "not_stated"),
    ("Clean the floor with water and a mop", "floor", None, None, "unknown", "water_and_mop_only"),
    ("Clean my ceramic and vinyl floor", "floor", None, None, "unknown", "not_stated"),
])
def test_surface_fields_are_composed(text, object_type, substrate, finish, surface, materials):
    result = resolve(text)
    assert (result.object_type, result.substrate, result.finish) == (object_type, substrate, finish)
    assert result.interpretation.surface == surface
    assert result.interpretation.materials == materials
    assert not result.allow_model


@pytest.mark.parametrize(("text", "device", "surface", "finish", "materials"), [
    ("I want to clean the screen of my iPhone", "iphone", "unknown", None, "not_stated"),
    ("Wiping my Apple iPhone display", "iphone", "unknown", None, "not_stated"),
    ("Clean my iPhone screen with water and a microfiber cloth",
     "iphone", "unknown", None, "water_and_microfiber_only"),
    ("Clean an iPhone screen protector", "iphone", "unknown", "screen_protector", "not_stated"),
    ("Clean my iPhone Duo screen", "iphone_duo", "unknown", None, "not_stated"),
    ("Clean my iPad screen", "ipad", "unknown", None, "not_stated"),
    ("Clean my iPad Air display", "ipad", "unknown", None, "not_stated"),
    ("Clean my nano-texture iPad Pro screen", "ipad", "unknown", "nano_texture", "not_stated"),
    ("Clean my iPad screen protector", "ipad", "unknown", "screen_protector", "not_stated"),
    ("I want to clean the screen of my Macbook", "macbook", "unknown", None, "not_stated"),
    ("Clean my MacBook Air display", "macbook", "unknown", None, "not_stated"),
    ("How do I wipe my MacBook Pro screen?", "macbook", "unknown", None, "not_stated"),
    ("Clean my nano-texture MacBook Pro screen", "macbook", "unknown", "nano_texture", "not_stated"),
    ("Clean the glass screen of my iPad", "ipad", "glass_screen", None, "not_stated"),
    ("Clean the glass screen of my MacBook", "macbook", "glass_screen", None, "not_stated"),
    ("Clean the glass screen of my iPhone", "iphone", "glass_screen", None, "not_stated"),
    ("Clean my nano-texture glass iPad screen", "ipad", "unknown", "nano_texture", "not_stated"),
    ("Clean my screen", None, "unknown", None, "not_stated"),
    ("I want to clean the screen of my laptop", "laptop", "unknown", None, "not_stated"),
    ("Cleaning the displays of my laptop computers", "laptop", "unknown", None, "not_stated"),
    ("Wiping my laptop’s display", "laptop", "unknown", None, "not_stated"),
    ("How do I make my notebook computer screen clean?", "laptop", "unknown", None, "not_stated"),
])
def test_screens_and_devices_are_matched_separately(text, device, surface, finish, materials):
    result = resolve(text)
    assert result.object_type == "screen"
    assert result.device == device
    assert result.interpretation.surface == surface
    assert result.finish == finish
    assert result.substrate == ("glass" if "glass" in text else None)
    assert result.interpretation.materials == materials
    assert not result.allow_model


def test_question_cooldown_and_provider_budget(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fixture")
    monkeypatch.setenv("TRANSLATION_PROVIDER", "llm")
    monkeypatch.setenv("LLM_REQUESTS_PER_MINUTE", "1")
    monkeypatch.delenv("QUESTION_COOLDOWN_SECONDS", raising=False)
    monkeypatch.delenv("TRUST_PROXY_CLIENT_IP", raising=False)
    now = 1000.0
    monkeypatch.setattr("homechem.main.monotonic", lambda: now)

    async def post(ip: str, question: str, **kwargs):
        transport = httpx.ASGITransport(app=app, client=(ip, 42000))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/interpret", json={"text": question}, **kwargs)

    async def run():
        nonlocal now
        async with app.router.lifespan_context(app):
            suggest = AsyncMock(return_value=Surface.GLASS_TABLE)
            app.state.provider.suggest_surface = suggest

            unclear = await post("192.0.2.1", "unclear")
            assert {key: value for key, value in unclear.json().items() if key != "presentation"} == {
                "surface": "unknown", "materials": "unknown", "method": "dictionary", "surface_term": None,
                "object_type": None, "device": None, "substrate": None, "finish": None, "translated_text": None, "translation_provider": None,
            }
            assert unclear.headers["x-request-id"]
            assert unclear.headers["cache-control"] == "no-store"

            same_ip = await post("::ffff:192.0.2.1", "Clean the oven", headers={"X-HomeChem-Client-IP": "192.0.2.9"})
            assert same_ip.status_code == 429
            assert same_ip.json()["limit"] == "question_cooldown"
            assert same_ip.headers["retry-after"] == "10"

            fallback = await post("192.0.2.2", "Clean my transparent dining surface")
            assert {key: value for key, value in fallback.json().items() if key != "presentation"} == {
                "surface": "glass_tabletop", "materials": "unknown", "method": "model",
                "surface_term": "glass_tabletop", "object_type": None, "device": None, "substrate": None, "finish": None, "translated_text": None, "translation_provider": None,
            }
            blocked = await post("192.0.2.3", "Clean my other transparent surface")
            assert blocked.status_code == 429
            assert blocked.json()["limit"] == "llm_budget"
            assert blocked.headers["retry-after"] == "60"

            now += 9
            early = await post("192.0.2.1", "Can I clean a glass tabletop?")
            assert early.headers["retry-after"] == "1"
            now += 1
            known = await post("192.0.2.1", "Can I clean a glass tabletop?")
            assert known.json()["method"] == "dictionary"
            assert known.json()["surface"] == "glass_tabletop"
            suggest.assert_awaited_once_with("Clean my transparent dining surface")

            app.state.trust_proxy_client_ip = True
            def forwarded(ip):
                return {"X-HomeChem-Client-IP": ip}

            first = await post("172.20.0.2", "Clean the oven", headers=forwarded("192.0.2.4"))
            second = await post("172.20.0.2", "Clean the oven", headers=forwarded("192.0.2.5"))
            duplicate = await post("172.20.0.2", "Clean the oven", headers=forwarded("192.0.2.4"))
            assert first.json()["surface_term"] == "oven"
            assert second.status_code == 200
            assert duplicate.status_code == 429

            now += 60
            english = await post("192.0.2.1", "How do I clean my laptop screen?")
            hebrew = await post("192.0.2.2", "איך מנקים את מסך המחשב הנייד?")
            translated = hebrew.json()
            assert translated.pop("translated_text") == "How do I clean my laptop screen?"
            original = english.json()
            assert original.pop("translated_text") is None
            assert translated.pop("translation_provider") == "llm"
            assert original.pop("translation_provider") is None
            assert translated == original
            assert translated["device"] == "laptop"
            translation_budget = await post("192.0.2.3", "איך מנקים את מסך המחשב הנייד?")
            assert translation_budget.status_code == 429
            assert translation_budget.json()["limit"] == "llm_budget"

            now += 60
            app.state.provider.translate_to_english = AsyncMock(return_value="מחשב נייד")
            unavailable = await post("192.0.2.3", "איך מנקים את מסך המחשב הנייד?")
            assert unavailable.status_code == 503
            assert unavailable.json()["detail"] == "translation_unavailable"
            suggest.assert_awaited_once()


    asyncio.run(run())
