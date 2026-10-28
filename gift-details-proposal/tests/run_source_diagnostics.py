"""Compile exact pinned client functions with data/TL adapters, without Telegram."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def braced(text, marker):
    start = text.index(marker)
    opening = text.index('{', start)
    depth = 0
    for pos in range(opening, len(text)):
        depth += (text[pos] == '{') - (text[pos] == '}')
        if depth == 0:
            return text[start:pos + 1]
    raise ValueError('Incomplete source function')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    package = Path(__file__).resolve().parent.parent
    manifest = json.loads((package / 'source-manifest.json').read_text(encoding='utf-8'))
    source = {}
    for name, record in manifest['files'].items():
        text = (args.source / name).read_text(encoding='utf-8')
        data = text.encode('utf-8')
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != record['git_blob_sha']:
            raise ValueError('Source does not match pinned Git blob: ' + name)
        source[name] = text
    credits = source['Telegram/SourceFiles/settings/settings_credits_graphics.cpp']
    api = source['Telegram/SourceFiles/api/api_credits.cpp']
    gate = braced(credits, 'bool UniqueGiftCanRemoveDetails(')
    reference = braced(api, 'MTPInputSavedStarGift InputSavedStarGiftId(')
    template = Path(__file__).with_name('source_harness.cpp.in').read_text(encoding='utf-8')
    program = template.replace('// @GATE@', gate).replace('// @REFERENCE@', reference)
    args.out.mkdir(parents=True, exist_ok=True)
    cpp = args.out / 'diagnostics.cpp'
    exe = args.out / ('diagnostics.exe' if os.name == 'nt' else 'diagnostics')
    cpp.write_text(program, encoding='utf-8')
    env = dict(os.environ)
    env['PATH'] = str(args.compiler.resolve().parent) + os.pathsep + env.get('PATH', '')
    command = [str(args.compiler.resolve()), '-std=c++20', '-O0', '-g',
               '-Wall', '-Wextra', '-Werror', str(cpp.resolve()), '-o', str(exe.resolve())]
    built = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
    if built.returncode:
        raise RuntimeError(built.stdout + built.stderr)
    run = subprocess.run([str(exe.resolve())], capture_output=True, text=True,
                         env=env, timeout=20)
    record = {
        'base_commit': manifest['ref'],
        'scope': 'Unmodified extracted client gate and gift reference function; synthetic data/TL adapters. No application build, payment, RPC or TON contract.',
        'compiler': subprocess.check_output([str(args.compiler.resolve()), '--version'], env=env).decode().splitlines()[0],
        'gate_sha256': hashlib.sha256(gate.encode()).hexdigest(),
        'reference_sha256': hashlib.sha256(reference.encode()).hexdigest(),
        'source_git_blobs_verified': len(source),
        'compile_exit_code': built.returncode,
        'test_exit_code': run.returncode,
        'output': run.stdout,
        'stderr': run.stderr,
    }
    (args.out / 'source-diagnostics.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))
    raise SystemExit(run.returncode)


if __name__ == '__main__':
    main()
