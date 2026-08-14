"""Make `pytest` test the tree it was invoked beside.

`langaccess` is normally installed editable, and the `.pth` that install leaves behind points at
whichever checkout was installed. Without this file a `pytest` run inside a second copy of the
package imports the INSTALLED one, so the tests pass or fail on code the author is not editing.

That is not hypothetical. On 2026-08-01 two people working on separate defects in the same working
copy each hit it, and one spent a stretch of the session reporting that fixtures it had just written
were failing, while the interpreter was importing a `core.py` that did not contain them.

The repository root is the parent of this file's parent, and `src/` beneath it is put FIRST on
`sys.path`, ahead of anything a `.pth` contributed. `test_the_import_is_the_tree_beside_these_tests`
below then fails loudly rather than silently if some future packaging change defeats it.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(os.path.dirname(_HERE), 'src')

if os.path.isdir(_SRC):
    # Ahead of the editable install's .pth, and ahead of any earlier copy already on the path.
    while _SRC in sys.path:
        sys.path.remove(_SRC)
    sys.path.insert(0, _SRC)


def test_the_import_is_the_tree_beside_these_tests():
    """The one test that has to run before the others are worth anything.

    Compares real paths, so a junction, a symlink or a drive-letter difference does not read as a
    mismatch when the file is the same file.
    """
    import langaccess

    imported = os.path.realpath(os.path.dirname(os.path.dirname(langaccess.__file__)))
    expected = os.path.realpath(_SRC)
    assert imported == expected, (
        'these tests are running against a different copy of langaccess than the one beside them.\n'
        '  imported: %s\n  expected: %s\n'
        'An editable install usually causes this. Run with PYTHONPATH set to the src directory '
        'above, or reinstall against this tree.' % (imported, expected)
    )
