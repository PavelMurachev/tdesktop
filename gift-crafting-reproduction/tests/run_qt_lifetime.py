"""Compile exact callbacks against real Qt and pinned crl/base headers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--qt', type=Path, required=True, help='Qt compiler prefix, e.g. ucrt64')
parser.add_argument('--sources', type=Path, required=True, help='Pinned base/crl/gsl source roots')
parser.add_argument('--work', type=Path, required=True)
parser.add_argument('--compiler', type=Path, help='Optional compatible Clang++ driver')
parser.add_argument('--sanitizer', choices=('none', 'address'), default='none')
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--baseline-ref', default='dd2a96c356971a0781f142826fcc212273f90098')
parser.add_argument('--test', help='One exact component scenario name')
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
    raise ValueError('Unterminated fragment')


info = source.index('crl::guard(box, [=] {', source.index('void ShowGiftCraftInfoBox('))
selection = source.index('crl::guard(box, [=](', source.index('void ShowSelectGiftBox('))
reply = source.index('[=](const MTPUpdates &result)', source.index('MTPpayments_CraftStarGift('))
fragments = '\n\n'.join((
    braced(source, source.index('bool ShowCraftLaterError(')),
    braced(source, source.index('bool ShowCraftAddressError(')),
    '''Fn<void()> MakeInfoStart(not_null<Window::SessionController*> controller,
        not_null<GenericBox*> box, std::shared_ptr<Data::UniqueGift> gift,
        Data::SavedStarGiftId savedId) { return ''' + braced(source, info) + '); }',
    '''Fn<void(std::shared_ptr<Data::UniqueGift>)> MakeSelection(
        not_null<GenericBox*> box, Fn<void(GiftForCraft)> chosen, bool firstSlot) {
        return ''' + braced(source, selection) + '); }',
    '''Fn<void(const MTPUpdates&)> MakeCraftResponse(Main::Session *session,
        [[maybe_unused]] not_null<Window::SessionController*> controller,
        const std::vector<GiftForCraft> &gifts,
        Fn<void(std::shared_ptr<Data::GiftUpgradeResult>)> done) { return '''
    + braced(source, reply) + '; }',
))
template = Path(__file__).with_name('qt_lifetime_harness.cpp').read_text(encoding='utf-8')
program = args.work / 'qt_lifetime.cpp'
program.write_text(template.replace('// @PRODUCTION_FRAGMENTS@', fragments), encoding='utf-8')
binary = args.work / 'qt_lifetime.exe'
compiler = args.compiler or (args.qt / 'bin/g++.exe')
command = [str(compiler), '-std=c++20', '-O0', '-g3', '-D_DEBUG',
           '-Wall', '-Wextra', '-Werror']
if args.compiler:
    standard = next((args.qt / 'include/c++').iterdir())
    command += ['-stdlib=libstdc++', '-nostdinc++',
                '-isystem', str(standard),
                '-isystem', str(standard / 'x86_64-w64-mingw32'),
                '-isystem', str(standard / 'backward'),
                '-L' + str(args.qt / 'lib/gcc/x86_64-w64-mingw32' / standard.name)]
if args.sanitizer == 'address':
    command += ['-fsanitize=address,undefined', '-fsanitize-trap=undefined',
                '-fno-omit-frame-pointer']
qt_include = args.qt / 'include/qt6' if (args.qt / 'include/qt6').exists() else args.qt / 'include'
for path in (qt_include, qt_include / 'QtCore', qt_include / 'QtGui',
             qt_include / 'QtWidgets', args.sources / 'base', args.sources / 'crl',
             args.sources / 'gsl/include'):
    command += ['-isystem', str(path)]
command += [str(program), '-L' + str(args.qt / 'lib'), '-lQt6Widgets', '-lQt6Gui', '-lQt6Core',
            '-o', str(binary)]
environment = os.environ.copy()
environment['PATH'] = (str(compiler.resolve().parent) + os.pathsep
                       + str((args.qt / 'bin').resolve()) + os.pathsep
                       + environment.get('PATH', ''))
environment['ASAN_OPTIONS'] = 'halt_on_error=1:abort_on_error=0:exitcode=86'
environment['QT_QPA_PLATFORM'] = 'offscreen'
plugins = next(path for path in (args.qt / 'share/qt6/plugins', args.qt / 'lib/qt6/plugins',
                                 args.qt / 'plugins') if (path / 'platforms/qoffscreen.dll').exists())
environment['QT_PLUGIN_PATH'] = str(plugins.resolve())
build = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=300)
for name in ('stdout', 'stderr'):
    (args.work / f'build.{name}.txt').write_text(getattr(build, name), encoding='utf-8')
record = {'source_sha256_lf': hashlib.sha256(source.encode()).hexdigest(),
          'mode': 'baseline' if args.baseline else 'patched',
          'baseline_ref': args.baseline_ref if args.baseline else None,
          'selected_test': args.test,
          'harness_sha256_lf': hashlib.sha256(template.encode()).hexdigest(),
          'build_exit_code': build.returncode, 'qt_platform': 'offscreen',
          'sanitizers': args.sanitizer,
          'scope': 'Real Qt and pinned crl/base; extracted callbacks; Session/data/UI adapters are doubles.'}
if build.returncode:
    (args.work / 'result.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(build.stderr)
    raise SystemExit(1)
run_command = [str(binary)] + ([args.test] if args.test else [])
run = subprocess.run(run_command, capture_output=True, text=True, env=environment, timeout=60)
for name in ('stdout', 'stderr'):
    (args.work / f'tests.{name}.txt').write_text(getattr(run, name), encoding='utf-8')
record['test_exit_code'] = run.returncode
record['compiler_version'] = subprocess.check_output(
    [str(compiler), '--version'], env=environment).decode(errors='replace').splitlines()[0]
record['runtime_version'] = run.stdout.splitlines()[0] if run.stdout else None
(args.work / 'result.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
print(run.stdout)
if run.stderr:
    print(run.stderr)
raise SystemExit(0 if run.returncode == 0 else 1)
