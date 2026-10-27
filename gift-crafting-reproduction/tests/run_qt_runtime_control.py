"""Build a minimal QApplication/ASan control with no Telegram code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--qt', type=Path, required=True)
parser.add_argument('--compiler', type=Path, required=True)
parser.add_argument('--work', type=Path, required=True)
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
source = Path(__file__).with_name('qt_runtime_control.cpp')
binary = args.work / 'qt_runtime_control.exe'
standard = next((args.qt / 'include/c++').iterdir())
qt_include = args.qt / 'include/qt6'
command = [str(args.compiler), '-std=c++20', '-O0', '-g3', '-D_DEBUG',
           '-Wall', '-Wextra', '-Werror', '-stdlib=libstdc++', '-nostdinc++',
           '-fsanitize=address,undefined', '-fsanitize-trap=undefined',
           '-fno-omit-frame-pointer']
for include in (standard, standard / 'x86_64-w64-mingw32', standard / 'backward',
                qt_include, qt_include / 'QtCore', qt_include / 'QtGui', qt_include / 'QtWidgets'):
    command.extend(['-isystem', str(include)])
command.extend(['-L' + str(args.qt / 'lib/gcc/x86_64-w64-mingw32' / standard.name),
                str(source), '-L' + str(args.qt / 'lib'), '-lQt6Widgets', '-lQt6Gui',
                '-lQt6Core', '-o', str(binary)])
environment = os.environ.copy()
environment['PATH'] = (str(args.compiler.resolve().parent) + os.pathsep
                       + str((args.qt / 'bin').resolve()) + os.pathsep
                       + environment.get('PATH', ''))
environment['QT_QPA_PLATFORM'] = 'offscreen'
environment['QT_PLUGIN_PATH'] = str((args.qt / 'share/qt6/plugins').resolve())
environment['ASAN_OPTIONS'] = 'halt_on_error=1:abort_on_error=0:exitcode=86'
build = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=300)
for name in ('stdout', 'stderr'):
    (args.work / f'build.{name}.txt').write_text(getattr(build, name), encoding='utf-8')
record = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'build_exit_code': build.returncode, 'contains_telegram_code': False,
          'sanitizers': 'ASan and UBSan trap'}
if build.returncode == 0:
    run = subprocess.run([str(binary)], capture_output=True, text=True,
                         env=environment, timeout=60)
    for name in ('stdout', 'stderr'):
        (args.work / f'tests.{name}.txt').write_text(getattr(run, name), encoding='utf-8')
    record['test_exit_code'] = run.returncode
    record['runtime_version'] = run.stdout.splitlines()[0] if run.stdout else None
(args.work / 'result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record))
raise SystemExit(0 if build.returncode == 0 and record['test_exit_code'] == 0 else 1)
