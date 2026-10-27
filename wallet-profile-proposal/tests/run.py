"""Compile extracted production wallet-profile logic with real Qt and rpl.

UserData, transport, amount painting and style adapters are intentionally synthetic.
No Telegram RPC, wallet keys or transfers are used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--qt', type=Path, required=True)
parser.add_argument('--deps', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--baseline-control', type=Path, help='Original source tree: the regression checks must fail')
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)

def braced(text, marker):
    start = text.index(marker)
    opening = text.index('{', start)
    depth = 0
    for i in range(opening, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError('Incomplete fragment')

directory = args.source / 'Telegram/SourceFiles/info/profile'
pill = (directory / 'info_profile_balance_pill.cpp').read_text(encoding='utf-8')
topbar = (directory / 'info_profile_top_bar.cpp').read_text(encoding='utf-8')
fragments = {
    'BALANCE_PRODUCER': braced(pill, '[[nodiscard]] rpl::producer<std::optional<int64>> ProfileBalanceValue('),
    'SET_CONTENT': braced(pill, 'void BalancePill::setContent('),
    'ACTIONABLE': braced(pill, 'bool BalancePill::actionable() const'),
    'CLICK_BODY': braced(topbar, 'pill->setClickedCallback([=] {').split('{', 1)[1][:-1],
}
if args.baseline_control:
    original = (args.baseline_control / 'Telegram/SourceFiles/info/profile/info_profile_balance_pill.cpp').read_text(encoding='utf-8')
    start = original.index('user->session().changes().peerFlagsValue(')
    end = original.index(' | rpl::distinct_until_changed()', start)
    stream = original[start:end]
    fragments['BALANCE_PRODUCER'] = (
        'rpl::producer<std::optional<int64>> ProfileBalanceValue(not_null<UserData*> user) { return '
        + stream + ' | rpl::map([](int64 value) -> std::optional<int64> {'
        + ' return value > 0 ? std::make_optional(value) : std::nullopt; }); }')
    fragments['SET_CONTENT'] = braced(original, 'void BalancePill::setContent(')
    topbar_before = (args.baseline_control / 'Telegram/SourceFiles/info/profile/info_profile_top_bar.cpp').read_text(encoding='utf-8')
    fragments['CLICK_BODY'] = braced(topbar_before, 'pill->setClickedCallback([=] {').split('{', 1)[1][:-1]
template = Path(__file__).with_name('harness.cpp.in').read_text(encoding='utf-8')
if args.baseline_control:
    template = template.replace(
        'void setContent(const QString &label, std::optional<int64> balance);',
        'void setContent(const QString &label, int64 balance);\n'
        '    void setContent(const QString &label, std::optional<int64> balance) { setContent(label, balance.value_or(0)); }')
for name, fragment in fragments.items():
    template = template.replace('// @' + name + '@', fragment)
program = args.out / 'harness.cpp'
program.write_text(template, encoding='utf-8')
compiler = args.qt / 'bin/g++.exe'
binary = args.out / 'wallet_profile_tests.exe'
command = [str(compiler), '-std=c++20', '-O0', '-g3', '-D_DEBUG', '-Wall', '-Wextra', '-Werror']
for path in [args.qt / 'include/qt6', *(args.qt / ('include/qt6/' + x) for x in ['QtCore', 'QtGui', 'QtWidgets']), *(args.deps / x for x in ['base', 'crl', 'rpl', 'gsl/include'])]:
    command += ['-isystem', str(path)]
command += [str(program), '-L' + str(args.qt / 'lib'), '-lQt6Widgets', '-lQt6Gui', '-lQt6Core', '-o', str(binary)]
environment = dict(os.environ)
environment['PATH'] = str((args.qt / 'bin').resolve()) + os.pathsep + environment.get('PATH', '')
environment['QT_QPA_PLATFORM'] = 'offscreen'
environment['QT_PLUGIN_PATH'] = str((args.qt / 'share/qt6/plugins').resolve())
record = {
    'mode': 'original negative control' if args.baseline_control else 'patched',
    'scope': 'Extracted production C++ fragments; real Qt Widgets and rpl; synthetic data and paint adapters; no full Telegram build or RPC.',
    'fragment_sha256': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in fragments.items()},
    'compiler': subprocess.check_output([str(compiler), '--version'], env=environment).decode().splitlines()[0],
}
build = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=180)
record['build_exit_code'] = build.returncode
(args.out / 'build.txt').write_text(build.stdout + build.stderr, encoding='utf-8')
if build.returncode:
    print(build.stderr)
else:
    run = subprocess.run([str(binary.resolve())], capture_output=True, text=True, env=environment, timeout=60)
    record['test_exit_code'] = run.returncode
    record['output'] = run.stdout
    record['stderr'] = run.stderr
    (args.out / 'tests.txt').write_text(run.stdout + run.stderr, encoding='utf-8')
    print(run.stdout + run.stderr)
(args.out / 'result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
expected_code = 1 if args.baseline_control else 0
raise SystemExit(0 if build.returncode == 0 and record.get('test_exit_code') == expected_code else 1)
