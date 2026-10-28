"""Verify that targeted acceptance tests detect deliberately broken model rules."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    source = (root / 'reference_service.py').read_text(encoding='utf-8')
    tests = (root / 'test_reference_service.py').read_text(encoding='utf-8')
    controls = [
        ('permanent_export_ban', "if not gift['live']:",
         "if gift['ever_exported']:\n            raise Rejected('historical_export_ban')\n        if not gift['live']:",
         'test_returned_gift_same_fee_and_result'),
        ('ownership_check_removed', 'if not permitted:', 'if False:',
         'test_other_user_cannot_quote'),
        ('durable_marker_check_removed', "if not gift['details'] or removed:",
         "if not gift['details']:", 'test_persisted_marker_blocks_stale_detail_write'),
        ('snapshot_marker_mask_removed', 'int(bool(details) and not removed)',
         'int(bool(details))', 'test_removed_details_stay_removed_after_export_return'),
        ('gift_revision_check_removed', "if (gift['owner'], gift['revision']) != (",
         "if False and (gift['owner'], gift['revision']) != (",
         'test_old_quote_invalid_after_export_and_return'),
        ('confirmation_check_removed', 'if confirmed is not True:', 'if False:',
         'test_requires_confirmation'),
    ]
    outcomes = []
    for label, before, after, test in controls:
        if source.count(before) != 1:
            raise ValueError('Mutation anchor not unique: ' + label)
        with tempfile.TemporaryDirectory(prefix='gift-details-negative-') as directory:
            destination = Path(directory)
            mutated = source.replace(before, after, 1)
            compile(mutated, 'reference_service.py', 'exec')
            (destination / 'reference_service.py').write_text(mutated, encoding='utf-8')
            (destination / 'test_reference_service.py').write_text(tests, encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', '-m', 'unittest',
                'test_reference_service.AcceptanceTests.' + test], cwd=destination,
                capture_output=True, text=True, timeout=20)
            detected = run.returncode != 0 and ('AssertionError' in run.stderr or
                "Rejected: historical_export_ban" in run.stderr)
            outcomes.append({'control': label, 'test': test,
                             'broken_rule_detected': detected})
    record = {
        'scope': 'Six deliberate mutations of the offline model only; not production defects or a Telegram backend baseline.',
        'reference_model_sha256_lf': hashlib.sha256(source.encode()).hexdigest(),
        'controls': outcomes,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))
    raise SystemExit(0 if all(item['broken_rule_detected'] for item in outcomes) else 1)


if __name__ == '__main__':
    main()
