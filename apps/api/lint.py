"""Dependency-free lint: syntax errors, unused imports, and duplicate top-level names. Exit 1 on any finding.
  python3 apps/api/lint.py [paths...]   (default: apps/api; tests can be passed explicitly)"""
import ast, sys
from pathlib import Path

def check(path):
    src = path.read_text(); out = []
    try: tree = ast.parse(src, str(path))
    except SyntaxError as e: return [f'{path}:{e.lineno}: syntax error: {e.msg}']
    imported = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names: imported[(a.asname or a.name).split('.')[0]] = n.lineno
        elif isinstance(n, ast.ImportFrom) and n.module != '__future__':
            for a in n.names:
                if a.name != '*': imported[a.asname or a.name] = n.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    exported = set()
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__all__' for t in n.targets):
            exported = {e.value for e in getattr(n.value, 'elts', []) if isinstance(e, ast.Constant)}
    if path.name not in ('__init__.py', 'server.py'):  # server.py is a facade that re-exports names on purpose
        for name, line in sorted(imported.items(), key=lambda x: x[1]):
            if name not in used and name not in exported and f'# noqa' not in src.splitlines()[line - 1]: out.append(f'{path}:{line}: unused import {name}')
    seen = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            if n.name in seen and not n.decorator_list: out.append(f'{path}:{n.lineno}: {n.name} redefined (first at line {seen[n.name]})')
            seen[n.name] = n.lineno
    return out

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    targets = [Path(a) for a in sys.argv[1:]] or [root / 'apps/api']
    files = [f for t in targets for f in ([t] if t.is_file() else sorted(t.rglob('*.py'))) if 'node_modules' not in f.parts]
    problems = [p for f in files for p in check(f)]
    print('\n'.join(problems) or f'lint: {len(files)} files clean'); sys.exit(1 if problems else 0)
