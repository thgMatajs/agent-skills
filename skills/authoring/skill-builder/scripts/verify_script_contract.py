#!/usr/bin/env python3
"""Static capability-contract check for scripts emitted by skill-builder.

Enforces the mechanically checkable part of the six-constraint contract in
references/branches.md (Branch: script). AST-based — the target is parsed,
never executed. Read-only, offline, stdlib-only.

Per file:
  stdlib only     every import resolves to the standard library
  offline         no network module: socket, ssl, urllib, http, ftplib,
                  smtplib, poplib, imaplib, xmlrpc, telnetlib
  process escape  no subprocess/multiprocessing/ctypes/pty import; no
                  os.system/os.popen/os.exec*/os.spawn*; no eval()/exec()
  deletes         no os.remove/os.unlink/os.rmdir/os.removedirs; no call of
                  .rmtree()/.unlink()/.rmdir() on any object
  secret reach    no os.environ/os.environb/os.getenv; no getpass/keyring
  declared I/O    module docstring present, mentioning usage and exit codes

Path containment (reads and writes only under the target directory) is not
statically decidable — it stays behavioral, reviewed at the pre-write
confirmation the skill requires.

Usage: python3 scripts/verify_script_contract.py <script.py> [more.py ...]
Exit:  0 all files pass | 1 any violation | 2 usage error or unparsable file
"""
import ast
import sys
from pathlib import Path

NETWORK_MODULES = {"socket", "ssl", "urllib", "http", "ftplib", "smtplib",
                   "poplib", "imaplib", "xmlrpc", "telnetlib"}
PROCESS_MODULES = {"subprocess", "multiprocessing", "ctypes", "pty"}
SECRET_MODULES = {"getpass", "keyring"}
OS_CALL_DENY = {"system", "popen", "remove", "unlink", "rmdir", "removedirs"}
ANY_ATTR_CALL_DENY = {"rmtree", "unlink", "rmdir"}
OS_ATTR_DENY = {"environ", "environb", "getenv"}
NAME_CALL_DENY = {"eval", "exec"}


def root_module(name):
    return name.split(".")[0]


def check_source(source, filename):
    violations = []
    tree = ast.parse(source, filename=filename)

    doc = ast.get_docstring(tree) or ""
    if not doc.strip():
        violations.append("declared I/O: module docstring missing")
    else:
        lowered = doc.lower()
        if "usage" not in lowered:
            violations.append("declared I/O: docstring does not state usage")
        if "exit" not in lowered:
            violations.append("declared I/O: docstring does not state exit codes")

    stdlib = getattr(sys, "stdlib_module_names", None)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [root_module(a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [root_module(node.module)] if node.module and node.level == 0 else []
        else:
            mods = []
        for mod in mods:
            if mod in NETWORK_MODULES:
                violations.append(f"offline: imports network module '{mod}'")
            if mod in PROCESS_MODULES:
                violations.append(f"process escape: imports '{mod}'")
            if mod in SECRET_MODULES:
                violations.append(f"secret reach: imports '{mod}'")
            if stdlib is not None and mod not in stdlib:
                violations.append(f"stdlib only: '{mod}' is not in the standard library")

        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in NAME_CALL_DENY:
                violations.append(f"process escape: calls {fn.id}()")
            if isinstance(fn, ast.Attribute):
                if (isinstance(fn.value, ast.Name) and fn.value.id == "os"
                        and (fn.attr in OS_CALL_DENY
                             or fn.attr.startswith(("exec", "spawn")))):
                    violations.append(f"process escape or delete: calls os.{fn.attr}()")
                elif fn.attr in ANY_ATTR_CALL_DENY:
                    violations.append(f"deletes: calls .{fn.attr}()")

        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os" and node.attr in OS_ATTR_DENY):
            violations.append(f"secret reach: reads os.{node.attr}")

    return violations


def main():
    paths = sys.argv[1:]
    if not paths:
        print("Usage: python3 .claude/skills/skill-builder/scripts/"
              "verify_script_contract.py <script.py> [more.py ...]")
        return 2

    failed = False
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            print(f"FAIL  {raw}: not a file")
            return 2
        try:
            violations = check_source(path.read_text(encoding="utf-8"), str(path))
        except SyntaxError as err:
            print(f"FAIL  {raw}: unparsable ({err.msg}, line {err.lineno})")
            return 2
        if violations:
            failed = True
            for violation in sorted(set(violations)):
                print(f"FAIL  {raw}: {violation}")
        else:
            print(f"OK    {raw}: capability contract holds "
                  f"(path containment stays behavioral)")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
