import pytest

from omni_webui._types import MutableBaseModel


class Pet(MutableBaseModel):
    name: str


def test_mutable_basemodel():
    cat = Pet.coerce("cat", {"name": "cat"})
    assert cat is not None
    cat.name = "kitty"
    assert cat.model_dump() == {"name": "kitty"}
    dog = Pet.coerce("dog", '{"name": "dog"}')
    pug = Pet.coerce("pug", dog)
    assert isinstance(pug, Pet)
    with pytest.raises(ValueError):
        Pet.coerce("not", True)
