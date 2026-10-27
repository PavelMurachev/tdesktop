"""Compile exact source fragments with test doubles; not a full Telegram build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', required=True, type=Path)
parser.add_argument('--compiler', required=True, type=Path, help='Clang++ or Zig executable')
parser.add_argument('--work', required=True, type=Path)
parser.add_argument('--cache', type=Path, help='Shared compiler cache for repeated runs')
parser.add_argument('--sanitizer', choices=['undefined', 'address'], default='undefined')
parser.add_argument('--test', help='Run one named scenario')
parser.add_argument('--baseline', action='store_true')
parser.add_argument('--baseline-ref', default='dd2a96c356971a0781f142826fcc212273f90098')
args = parser.parse_args()
args.work.mkdir(parents=True, exist_ok=True)
source_path = 'Telegram/SourceFiles/boxes/star_gift_craft_box.cpp'
if args.baseline:
    source = subprocess.check_output([
        'git', '-c', f'safe.directory={args.repo.resolve().as_posix()}',
        '-C', str(args.repo), 'show', f'{args.baseline_ref}:{source_path}']).decode('utf-8')
else:
    source = (args.repo / source_path).read_text(encoding='utf-8')
settings_path = 'Telegram/SourceFiles/settings/settings_credits_graphics.cpp'
if args.baseline:
    settings = subprocess.check_output([
        'git', '-c', f'safe.directory={args.repo.resolve().as_posix()}',
        '-C', str(args.repo), 'show', f'{args.baseline_ref}:{settings_path}']).decode('utf-8')
else:
    settings = (args.repo / settings_path).read_text(encoding='utf-8')


def braced(text, start):
    opening = text.index('{', start)
    depth = 0
    quote = None
    escaped = False
    position = opening
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


info_start = source.index('void ShowGiftCraftInfoBox(')
info_start = source.index('crl::guard(box, [=] {', info_start)
info = braced(source, info_start) + ')'
selection_start = source.index('void ShowSelectGiftBox(')
selection_start = source.index('crl::guard(box, [=](', selection_start)
selection = braced(source, selection_start) + ')'
reply_start = source.index('MTPpayments_CraftStarGift(')
reply_start = source.index('[=](const MTPUpdates &result)', reply_start)
reply = braced(source, reply_start)
failure_start = source.index('[=](const MTP::Error &error)', reply_start)
failure = braced(source, failure_start)
start_gate = source.index('const auto startCrafting = [=] {')
start_gate = source.index('{', start_gate) + 1
start_gate_end = source.index('const auto &cs = state->craftState;', start_gate)
start_gate = source[start_gate:start_gate_end]
eligibility_start = settings.index('bool CanCraftGift(')
eligibility = braced(settings, eligibility_start)
cooldown_start = source.index('bool ShowCraftLaterError(')
cooldown = braced(source, cooldown_start)
address_start = source.index('bool ShowCraftAddressError(')
address = braced(source, address_start)
picker_function = braced(source, source.index('void ShowSelectGiftBox('))
picker_loading = picker_function[picker_function.index(
    'const auto show = crl::guard(controller, [=] {'):-1]
fragments = '\n\n'.join([
    cooldown,
    address,
    eligibility,
    '''Fn<void()> MakeInfoStart(not_null<Window::SessionController*> controller,
        not_null<GenericBox*> box, std::shared_ptr<Data::UniqueGift> gift,
        Data::SavedStarGiftId savedId) { return ''' + info + '; }',
    '''Fn<void(std::shared_ptr<Data::UniqueGift>)> MakeSelection(
        not_null<GenericBox*> box, Fn<void(GiftForCraft)> chosen,
        bool firstSlot) { return ''' + selection + '; }',
    '''Fn<void(const MTPUpdates&)> MakeCraftResponse(
        Main::Session *session,
        [[maybe_unused]] not_null<Window::SessionController*> controller,
        const std::vector<GiftForCraft> &gifts,
        Fn<void(std::shared_ptr<Data::GiftUpgradeResult>)> done) { return '''
        + reply + '; }',
    'Fn<void(const MTP::Error&)> MakeCraftError(Fn<void(CraftResult)> done) { return '
        + failure + '; }',
    '''Fn<void()> MakeStartGate(std::shared_ptr<StartState> state,
        not_null<GenericBox*> box, Fn<void()> dispatch) {
        return [=] { ''' + start_gate + ' dispatch(); }; }',
])
fragments += '''\nvoid RunPickerLoad(not_null<Window::SessionController*> controller,
    [[maybe_unused]] bool allowResale) {
    const auto session = &controller->session();
    const auto giftId = 42ULL;
    const auto state = std::make_shared<PickerLoadState>();
    const auto make = [] {};
    ''' + picker_loading + '}'
template = Path(__file__).with_name('fragment_harness.cpp').read_text(encoding='utf-8')
support = Path(__file__).with_name('picker_loading_support.inc').read_text(encoding='utf-8')
program = args.work / 'fragments.cpp'
program.write_text(template.replace('// @PICKER_LOADING_SUPPORT@', support)
                   .replace('// @PRODUCTION_FRAGMENTS@', fragments), encoding='utf-8')
binary = args.work / 'fragments.exe'
environment = os.environ.copy()
environment['ZIG_GLOBAL_CACHE_DIR'] = str(args.cache or (args.work / 'zig-cache'))
environment['ZIG_LOCAL_CACHE_DIR'] = str(args.work / 'zig-local-cache')
environment['PATH'] = str(args.compiler.resolve().parent) + os.pathsep + environment.get('PATH', '')
command = [str(args.compiler)]
if args.compiler.stem.lower() == 'zig':
    command += ['c++']
command += ['-std=c++20', '-O0', '-g',
           '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined',
           '-fsanitize-trap=undefined']
if args.sanitizer == 'address':
    command += ['-fsanitize=address', '-fno-omit-frame-pointer']
    environment['ASAN_OPTIONS'] = 'halt_on_error=1:abort_on_error=0:exitcode=86'
command += [str(program), '-o', str(binary)]
build = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=1200)
(args.work / 'build.stdout.txt').write_text(build.stdout, encoding='utf-8')
(args.work / 'build.stderr.txt').write_text(build.stderr, encoding='utf-8')
record = {'mode': 'baseline' if args.baseline else 'patched',
          'baseline_ref': args.baseline_ref if args.baseline else None,
          'sanitizer': args.sanitizer,
          'source_sha256_lf': hashlib.sha256(source.encode()).hexdigest(),
          'settings_sha256_lf': hashlib.sha256(settings.encode()).hexdigest(),
          'harness_sha256_lf': hashlib.sha256(template.encode()).hexdigest(),
          'loading_support_sha256_lf': hashlib.sha256(support.encode()).hexdigest(),
          'build_exit_code': build.returncode,
          'compiler_flags': command[(2 if args.compiler.stem.lower() == 'zig' else 1):-3],
          'scope': 'Extracted C++ source; fake UI, transport and lifetime guard. Not Qt or server tests.'}
if build.returncode:
    print(build.stderr)
    (args.work / 'result.json').write_text(json.dumps(record, indent=2))
    raise SystemExit(build.returncode)
run_command = [str(binary)]
if args.test:
    run_command += [args.test]
execution = subprocess.run(run_command, capture_output=True, text=True, env=environment, timeout=60)
(args.work / 'tests.stdout.txt').write_text(execution.stdout, encoding='utf-8')
(args.work / 'tests.stderr.txt').write_text(execution.stderr, encoding='utf-8')
record['test_exit_code'] = execution.returncode
record['selected_test'] = args.test
(args.work / 'result.json').write_text(json.dumps(record, indent=2))
print(execution.stdout)
if execution.stderr:
    print(execution.stderr)
raise SystemExit(execution.returncode)
