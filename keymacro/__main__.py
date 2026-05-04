"""Allow ``python -m keymacro ...`` to invoke the CLI.

Uses an absolute import (``keymacro.cli`` rather than ``.cli``) so the
same file works as both:

* a ``-m`` entry point (where the package context is set up automatically), and
* a PyInstaller bundle entry script (where the file is run as a top-level
  script with no ``__package__`` — relative imports would raise
  ``ImportError: attempted relative import with no known parent package``).
"""

from keymacro.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
