"""The graphical editor of the parameter list.

The GUI is a small local web application: a Python server (standard library
only) plus three files in ``web/``.  Nothing has to be installed - the browser
that is already on the machine renders it.

    server.py     the HTTP server and the routing
    api.py        one method per action the front end can call
    document.py   the parameter list being edited, plus undo/redo
    web/          index.html + style.css + api.js / grid.js / editor.js / app.js
"""

__all__ = ["server", "api", "document"]
