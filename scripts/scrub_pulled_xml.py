#!/usr/bin/env python3
"""Remove platform metadata from pulled Boomi component XML before committing.

A pull (boomi-component-pull.sh) stamps the root <bns:Component> tag with who created and modified the
component, timestamps, the branch and the folder path. None of that is needed to use the file as a
template, and the creator is a person's email address. This removes those attributes from the root tag
and nothing else; componentId, version, name, type, subType and folderId are kept.

    python3 scripts/scrub_pulled_xml.py            # scrub every XML under active-development/
    python3 scripts/scrub_pulled_xml.py <file>...  # scrub only these files
"""
from __future__ import annotations

import re
import sys
import xml.dom.minidom as minidom
from pathlib import Path

DROP = ("createdBy", "modifiedBy", "createdDate", "modifiedDate", "folderFullPath", "folderName",
        "branchName", "branchId", "deleted", "currentVersion")
ROOT_TAG = re.compile(r"<bns:Component\b[^>]*>")


def scrub(text: str) -> str:
    match = ROOT_TAG.search(text)
    if not match:
        return text
    tag = new = match.group(0)
    for name in DROP:
        new = re.sub(r'\s+%s="[^"]*"' % name, "", new)
    return text.replace(tag, new, 1)


def main(argv) -> int:
    root = Path(__file__).resolve().parent.parent / "active-development"
    files = [Path(a) for a in argv] or sorted(p for p in root.rglob("*.xml") if p.is_file())
    changed = 0
    for path in files:
        original = path.read_text(encoding="utf-8")
        cleaned = scrub(original)
        if cleaned == original:
            continue
        minidom.parseString(cleaned.encode("utf-8"))  # must still be well-formed
        path.write_text(cleaned, encoding="utf-8")
        changed += 1
        print("scrubbed", path)
    print("%d file(s) changed" % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
