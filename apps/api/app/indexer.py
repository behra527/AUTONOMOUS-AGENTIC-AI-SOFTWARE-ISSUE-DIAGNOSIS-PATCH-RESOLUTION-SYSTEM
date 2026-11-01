"""Read Git objects without checking out, importing, or executing repository code."""
import ast
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import urlparse
from .config import settings

IGNORE = {'.git', '.venv', 'venv', 'node_modules', 'dist', 'build', '__pycache__', 'vendor', '.aws', '.ssh'}
SECRET = re.compile(r'-----BEGIN .*PRIVATE KEY-----|(?:api[_-]?key|password|secret|token)\s*[:=]\s*[\"\'][^\"\']{8,}', re.I)


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def validate_remote(remote):
    parsed = urlparse(remote)
    if parsed.scheme == 'https':
        hosts = settings.git_allowed_hosts.split(',')
        if parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.query or parsed.fragment:
            raise ValueError('Use a credential-free HTTPS URL on an allowed Git host')
        return remote
    # Local repositories are deliberately limited to an operator-configured root.
    path = Path(remote).resolve()
    root = settings.local_repo_root.resolve()
    if not path.is_relative_to(root) or not path.is_dir():
        raise ValueError('Local repository is outside the configured repository root')
    return str(path)


def git(*args, timeout=90):
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_LFS_SKIP_SMUDGE': '1'}
    result = subprocess.run(['git', '-c', 'core.hooksPath=', '-c', 'protocol.ext.allow=never',
                             '-c', 'http.followRedirects=false', *map(str, args)],
                            capture_output=True, timeout=timeout, env=env)
    if result.returncode:
        raise ValueError('Git operation failed; check repository access and pinned commit')
    return result.stdout


def source_objects(repo_id, remote, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('An exact 40-character Git commit is required')
    remote = validate_remote(remote)
    target = settings.data_dir / 'repositories' / repo_id
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        git('clone', '--bare', '--no-local', '--', remote, target)
    else:
        git('-C', target, 'fetch', '--no-tags', remote)
    actual = git('-C', target, 'rev-parse', '--verify', f'{commit}^{{commit}}').decode().strip()
    if actual != commit:
        raise ValueError('Snapshot identity mismatch')
    tree = git('-C', target, 'ls-tree', '-r', '-z', commit)
    entries = tree.split(b'\0')
    if len(entries) > 20001:
        raise ValueError('Repository exceeds 20,000 entries')
    total = 0
    for entry in entries:
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        path = raw_path.decode('utf-8', errors='replace')
        p = PurePosixPath(path)
        if mode not in ('100644', '100755') or kind != 'blob' or any(x in IGNORE or x.startswith('.') for x in p.parts):
            continue
        if p.suffix.lower() not in ('.py', '.md', '.rst', '.txt') or any(x in p.name.lower() for x in ('secret', 'credential', 'lock')):
            continue
        size = int(git('-C', target, 'cat-file', '-s', oid))
        if size > 200_000:
            continue
        total += size
        if total > 8_000_000:
            raise ValueError('Repository text exceeds 8 MB indexing quota')
        text = git('-C', target, 'cat-file', 'blob', oid).decode('utf-8', errors='replace')
        if '\x00' in text or SECRET.search(text):
            continue
        yield path, text


def extract(path, text):
    lines = text.splitlines()
    result = []

    def add(symbol, kind, start, end, metadata=None):
        # Bound source sent to the model, retaining exact line references.
        for offset in range(start, end + 1, 100):
            stop = min(offset + 99, end)
            content = '\n'.join(lines[offset - 1:stop])
            result.append(dict(path=path, symbol=symbol, kind=kind, start_line=offset,
                               end_line=stop, content=content, content_hash=digest(content), metadata_=metadata or {}))

    if path.endswith('.py'):
        tree = ast.parse(text, filename=path)
        imports = [ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]

        def walk(node, prefix=''):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = f'{prefix}.{child.name}'.strip('.')
                    calls = sorted({ast.unparse(n.func) for n in ast.walk(child) if isinstance(n, ast.Call)})
                    add(name, type(child).__name__, child.lineno, child.end_lineno, {'imports': imports, 'call_candidates': calls})
                    walk(child, name)
                else:
                    walk(child, prefix)
        walk(tree)
        # Includes constants and imports, which can be causal evidence in their own right.
        add('<module>', 'module', 1, len(lines), {'imports': imports})
    else:
        add('<document>', 'document', 1, len(lines))
    return result
