"""Writes lab/index.html: template.html with data.js inlined."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(HERE, "template.html")).read()
d = open(os.path.join(HERE, "data.js")).read()
open(os.path.join(HERE, "index.html"), "w").write(t.replace("/*DATA*/", d))
