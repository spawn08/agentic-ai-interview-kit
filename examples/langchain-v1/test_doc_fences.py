"""Regression tests for the shared Python-fence syntax/import extractor."""
import ast

import pytest

from check_doc_imports import python_blocks


@pytest.mark.parametrize("fence", ["```", "~~~"])
@pytest.mark.parametrize("lang", ["python", "python3", "py", "py3"])
@pytest.mark.parametrize("indent", ["", "   "])
def test_python_fence_forms(fence, lang, indent):
    text = f"# example\n{indent}{fence}{lang}\n{indent}value = 1\n{indent}{fence}\n"
    blocks = list(python_blocks(text))
    assert blocks == [(3, "value = 1\n")]
    ast.parse(blocks[0][1])


def test_other_fences_do_not_expose_nested_python_markup():
    text = "~~~~text\n~~~python3\ninvalid python!\n~~~\n~~~~\n"
    assert list(python_blocks(text)) == []


def test_closing_fence_must_match_character_and_minimum_length():
    text = "~~~~python3\ntext = '''\n```\n~~~\n'''\n~~~~~\n"
    blocks = list(python_blocks(text))
    assert len(blocks) == 1
    ast.parse(blocks[0][1])
    assert "```\n~~~" in blocks[0][1]


def test_unclosed_tilde_fence_is_an_error():
    with pytest.raises(ValueError, match="unclosed code fence opened at line 1"):
        list(python_blocks("~~~python3\nvalue = 1\n```\n"))


def test_partial_opener_indentation_is_removed_from_body():
    blocks = list(python_blocks("   ~~~py\n  value = 1\n   ~~~\n"))
    assert blocks == [(2, "value = 1\n")]
