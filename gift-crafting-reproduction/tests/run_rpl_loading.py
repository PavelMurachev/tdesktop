"""Compile the production picker loading tail with real pinned reactive libraries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--qt', type=Path, required=True)
parser.add_argument('--sources', type=Path, required=True)
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--compiler', type=Path)
parser.add_argument('--sanitizer', choices=('none', 'address'), default='none')
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--baseline-ref', default='dd2a96c356971a0781f142826fcc212273f90098')
parser.add_argument('--test')
parser.add_argument('--sequences', action='store_true', help='Bounded functional event sequence checks')
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
source_path = 'Telegram/SourceFiles/boxes/star_gift_craft_box.cpp'
if args.baseline:
    source = subprocess.check_output([
        'git', '-c', f'safe.directory={args.repo.resolve().as_posix()}',
        '-C', str(args.repo), 'show', f'{args.baseline_ref}:{source_path}']).decode('utf-8')
else:
    source = (args.repo / source_path).read_text(encoding='utf-8')


def braced(text, start):
    opening = text.index('{', start)
    depth, quote, escaped, position = 0, None, False, opening
    while position < len(text):
        char = text[position]
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif text.startswith('//', position):
            end = text.find('\n', position)
            position = len(text) if end < 0 else end
            continue
        elif text.startswith('/*', position):
            end = text.find('*/', position + 2)
            if end < 0:
                raise ValueError('Unterminated comment')
            position = end + 2
            continue
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:position + 1]
        position += 1
    raise ValueError('Unterminated source fragment')


function = braced(source, source.index('void ShowSelectGiftBox('))
tail = function[function.index('const auto show = crl::guard(controller, [=] {'):-1]
harness_path = Path(__file__).with_name('rpl_loading_harness.cpp')
harness = harness_path.read_text(encoding='utf-8')
program = args.work / 'rpl_loading.cpp'
program.write_text(harness.replace('// @PRODUCTION_LOADING@', tail), encoding='utf-8')
sequence_template = None
if args.sequences:
    sequence_template = Path(__file__).with_name('rpl_sequence_harness.cpp').read_text(encoding='utf-8')
    program = args.work / 'rpl_sequences.cpp'
    program.write_text(sequence_template, encoding='utf-8')
binary = args.work / 'rpl_loading.exe'
compiler = args.compiler or (args.qt / 'bin/g++.exe')
command = [str(compiler), '-std=c++20', '-O0', '-g3', '-D_DEBUG', '-Wall', '-Wextra', '-Werror']
if args.compiler:
    standard = next((args.qt / 'include/c++').iterdir())
    command += ['-stdlib=libstdc++', '-nostdinc++']
    for path in (standard, standard / 'x86_64-w64-mingw32', standard / 'backward'):
        command += ['-isystem', str(path)]
    command += ['-L' + str(args.qt / 'lib/gcc/x86_64-w64-mingw32' / standard.name)]
if args.sanitizer == 'address':
    command += ['-fsanitize=address,undefined', '-fsanitize-trap=undefined', '-fno-omit-frame-pointer']
for path in (args.qt / 'include/qt6', args.qt / 'include/qt6/QtCore', args.sources / 'base',
             args.sources / 'crl', args.sources / 'rpl', args.sources / 'gsl/include'):
    command += ['-isystem', str(path)]
command += [str(program), '-L' + str(args.qt / 'lib'), '-lQt6Core', '-o', str(binary)]
environment = os.environ.copy()
environment['PATH'] = (str(compiler.resolve().parent) + os.pathsep
                       + str((args.qt / 'bin').resolve()) + os.pathsep
                       + environment.get('PATH', ''))
environment['ASAN_OPTIONS'] = 'halt_on_error=1:abort_on_error=0:exitcode=86'
record = {
    'mode': 'baseline' if args.baseline else 'patched',
    'baseline_ref': args.baseline_ref if args.baseline else None,
    'source_sha256_lf': hashlib.sha256(source.encode()).hexdigest(),
    'loading_tail_sha256_lf': hashlib.sha256(tail.encode()).hexdigest(),
    'harness_sha256_lf': hashlib.sha256(harness.encode()).hexdigest(),
    'sanitizer': args.sanitizer,
    'selected_test': args.test,
    'sequence_probe': args.sequences,
    'sequence_harness_sha256_lf': hashlib.sha256(sequence_template.encode()).hexdigest() if sequence_template else None,
    'compiler_flags': command[1:],
    'scope': 'Real pinned rpl/base/crl/GSL and QtCore; extracted loading tail; data/transport/UI adapters.',
}
build = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=300)
record['build_exit_code'] = build.returncode
for name in ('stdout', 'stderr'):
    (args.work / f'build.{name}.txt').write_text(getattr(build, name), encoding='utf-8')
if build.returncode == 0:
    run = subprocess.run([str(binary.resolve())] + ([args.test] if args.test else []),
                         capture_output=True, text=True, env=environment, timeout=60,
                         cwd=args.work.resolve() if args.sequences else None)
    record['test_exit_code'] = run.returncode
    record['runtime_version'] = run.stdout.splitlines()[0] if run.stdout else None
    if args.sequences and (args.work / 'sequence-observations.txt').exists():
        record['sequence_trace_sha256'] = hashlib.sha256(
            (args.work / 'sequence-observations.txt').read_bytes()).hexdigest()
    for name in ('stdout', 'stderr'):
        (args.work / f'tests.{name}.txt').write_text(getattr(run, name), encoding='utf-8')
    print(run.stdout)
    if run.stderr:
        print(run.stderr)
else:
    print(build.stderr)
record['compiler_version'] = subprocess.check_output(
    [str(compiler), '--version'], env=environment).decode(errors='replace').splitlines()[0]
(args.work / 'result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if build.returncode == 0 and record['test_exit_code'] == 0 else 1)
