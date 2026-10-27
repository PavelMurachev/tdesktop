"""Offline protocol model. Synthetic assets only; no Telegram, wallet or TON I/O."""
from contextlib import contextmanager
import hashlib
import json
import sqlite3
import uuid


class Rejected(Exception):
    pass


class SimulatedCrash(Exception):
    pass


@contextmanager
def transaction(path):
    db = sqlite3.connect(path, timeout=20, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


class MockSettlement:
    """Separate durable fake ledger; assumes verified exclusive custody upstream.

    This is deliberately NOT a signature verifier, NFT contract or custody flow.
    All synthetic inputs use this adapter to exercise distributed recovery.
    """
    def __init__(self, path):
        self.path = path
        with transaction(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS spent (gift TEXT PRIMARY KEY, op TEXT NOT NULL)')

    def consume(self, gift, op):
        with transaction(self.path) as db:
            previous = db.execute('SELECT op FROM spent WHERE gift=?', (gift,)).fetchone()
            if previous and previous['op'] != op:
                raise Rejected('external_conflict')
            db.execute('INSERT OR IGNORE INTO spent VALUES (?,?)', (gift, op))

    def count(self):
        with transaction(self.path) as db:
            return db.execute('SELECT COUNT(*) FROM spent').fetchone()[0]


class Model:
    def __init__(self, path, settlement, draw=lambda: 0):
        self.path, self.settlement, self.draw = path, settlement, draw
        with transaction(path) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS gifts (
                    id TEXT PRIMARY KEY, owner TEXT, kind TEXT, chance INTEGER,
                    location TEXT, exported INTEGER, cooldown INTEGER,
                    listed INTEGER DEFAULT 0, consumed INTEGER DEFAULT 0,
                    reserved TEXT);
                CREATE TABLE IF NOT EXISTS policies (
                    kind TEXT PRIMARY KEY, version INTEGER, enabled INTEGER);
                CREATE TABLE IF NOT EXISTS rights (
                    actor TEXT, owner TEXT, PRIMARY KEY(actor,owner));
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, actor TEXT, owner TEXT, request_key TEXT,
                    fingerprint TEXT, inputs TEXT, version INTEGER, expires INTEGER,
                    state TEXT, chance INTEGER, won INTEGER, result TEXT,
                    UNIQUE(actor,request_key));
                CREATE TABLE IF NOT EXISTS outputs (
                    id TEXT PRIMARY KEY, operation TEXT UNIQUE, owner TEXT, kind TEXT);
            ''')

    def add_gift(self, ident, owner='alice', kind='bells', chance=250,
                 location='telegram', exported=False, cooldown=0):
        if location not in ('telegram', 'ton') or not 0 <= chance <= 1000:
            raise ValueError('Invalid synthetic fixture')
        with transaction(self.path) as db:
            db.execute('INSERT INTO gifts(id,owner,kind,chance,location,exported,cooldown) VALUES (?,?,?,?,?,?,?)',
                       (ident, owner, kind, chance, location, int(exported), cooldown))
            db.execute('INSERT OR IGNORE INTO policies VALUES (?,1,1)', (kind,))

    def permission(self, actor, owner, allowed):
        with transaction(self.path) as db:
            if allowed:
                db.execute('INSERT OR IGNORE INTO rights VALUES (?,?)', (actor, owner))
            else:
                db.execute('DELETE FROM rights WHERE actor=? AND owner=?', (actor, owner))

    @staticmethod
    def authorize(db, actor, owner):
        if actor != owner and not db.execute('SELECT 1 FROM rights WHERE actor=? AND owner=?',
                                             (actor, owner)).fetchone():
            raise Rejected('owner_authorization_required')

    @staticmethod
    def validate(db, inputs, owner, version, now, op=None):
        gifts = []
        for ident in inputs:
            row = db.execute('SELECT * FROM gifts WHERE id=?', (ident,)).fetchone()
            if row is None:
                raise Rejected('unknown_input')
            if row['owner'] != owner:
                raise Rejected('wrong_owner')
            if row['consumed'] or row['listed'] or row['cooldown'] > now:
                raise Rejected('input_unavailable')
            if row['reserved'] is not None and row['reserved'] != op:
                raise Rejected('already_reserved')
            gifts.append(row)
        if len({r['kind'] for r in gifts}) != 1:
            raise Rejected('mixed_types')
        policy = db.execute('SELECT * FROM policies WHERE kind=?', (gifts[0]['kind'],)).fetchone()
        if not policy or not policy['enabled'] or policy['version'] != version:
            raise Rejected('recipe_changed_or_disabled')
        return gifts

    def prepare(self, actor, owner, inputs, request_key, now=0, ttl=60, version=1):
        if not request_key or not 1 <= len(inputs) <= 4 or len(set(inputs)) != len(inputs) or ttl <= 0:
            raise Rejected('invalid_request')
        inputs = sorted(inputs)  # Canonical IDs, never display slugs; no primary slot.
        fingerprint = hashlib.sha256(json.dumps([owner, inputs, version]).encode()).hexdigest()
        with transaction(self.path) as db:
            self.authorize(db, actor, owner)
            old = db.execute('SELECT * FROM operations WHERE actor=? AND request_key=?',
                             (actor, request_key)).fetchone()
            if old:
                if old['fingerprint'] != fingerprint:
                    raise Rejected('idempotency_conflict')
                return self.public(old)
            gifts = self.validate(db, inputs, owner, version, now)
            chance = sum(r['chance'] for r in gifts)
            if chance > 1000:
                raise Rejected('invalid_recipe_probability')
            op = 'op-' + uuid.uuid4().hex
            db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (op, actor, owner, request_key, fingerprint, json.dumps(inputs),
                        version, now + ttl, 'prepared', chance, None, None))
            for ident in inputs:
                db.execute('UPDATE gifts SET reserved=? WHERE id=?', (op, ident))
            return self.public(db.execute('SELECT * FROM operations WHERE id=?', (op,)).fetchone())

    @staticmethod
    def public(row):
        # Do not disclose a stored outcome while settlement remains incomplete.
        return {k: row[k] for k in ('id', 'state', 'expires', 'chance')} | {
            'inputs': json.loads(row['inputs']),
            'result': row['result'] if row['state'] == 'succeeded' else None}

    @staticmethod
    def owned_operation(db, actor, op):
        row = db.execute('SELECT * FROM operations WHERE id=?', (op,)).fetchone()
        if row is None or row['actor'] != actor:
            raise Rejected('operation_not_accessible')
        return row

    def get(self, actor, op):
        with transaction(self.path) as db:
            return self.public(self.owned_operation(db, actor, op))

    def commit(self, actor, op, now=0, verified_ton_inputs=(), crash_at=None):
        with transaction(self.path) as db:
            row = self.owned_operation(db, actor, op)
            if row['state'] in ('succeeded', 'failed'):
                return self.public(row)
            if row['state'] == 'cancelled':
                raise Rejected('cancelled')
            if row['state'] == 'prepared':
                if now >= row['expires']:
                    raise Rejected('expired')
                self.authorize(db, actor, row['owner'])
                gifts = self.validate(db, json.loads(row['inputs']), row['owner'], row['version'], now, op)
                if sum(r['chance'] for r in gifts) != row['chance']:
                    raise Rejected('quote_changed')
                # Test-only seam: caller is the trusted adapter, NOT a user RPC.
                # Real deployment must verify exclusive custody bound to this op.
                if any(r['location'] == 'ton' and (op, r['id']) not in verified_ton_inputs for r in gifts):
                    raise Rejected('verified_custody_required')
                draw = self.draw()
                if not 0 <= draw < 1000:
                    raise ValueError('Invalid synthetic outcome draw')
                db.execute('UPDATE operations SET state=?,won=? WHERE id=?',
                           ('committed', int(draw < row['chance']), op))
        if crash_at == 'after_decision':
            raise SimulatedCrash(crash_at)
        return self.resume(actor, op, crash_at)

    def resume(self, actor, op, crash_at=None):
        with transaction(self.path) as db:
            row = self.owned_operation(db, actor, op)
            if row['state'] in ('succeeded', 'failed'):
                return self.public(row)
            if row['state'] != 'committed':
                raise Rejected('not_committed')
            inputs = json.loads(row['inputs'])
        for index, ident in enumerate(inputs):
            self.settlement.consume(ident, op)
            if index == 0 and crash_at == 'after_first_receipt':
                raise SimulatedCrash(crash_at)
        if crash_at == 'before_publication':
            raise SimulatedCrash(crash_at)
        with transaction(self.path) as db:
            row = self.owned_operation(db, actor, op)
            if row['state'] != 'committed':
                return self.public(row)
            result = 'result-' + op if row['won'] else None
            if result:
                kind = db.execute('SELECT kind FROM gifts WHERE id=?', (inputs[0],)).fetchone()[0]
                db.execute('INSERT INTO outputs VALUES (?,?,?,?)', (result, op, row['owner'], kind))
            for ident in inputs:
                db.execute('UPDATE gifts SET consumed=1,reserved=NULL WHERE id=?', (ident,))
            db.execute('UPDATE operations SET state=?,result=? WHERE id=?',
                       ('succeeded' if result else 'failed', result, op))
            return self.public(db.execute('SELECT * FROM operations WHERE id=?', (op,)).fetchone())

    def cancel(self, actor, op):
        with transaction(self.path) as db:
            row = self.owned_operation(db, actor, op)
            if row['state'] == 'cancelled':
                return self.public(row)
            if row['state'] != 'prepared':
                raise Rejected('already_committed')
            db.execute('UPDATE gifts SET reserved=NULL WHERE reserved=?', (op,))
            db.execute('UPDATE operations SET state=? WHERE id=?', ('cancelled', op))
            return self.public(db.execute('SELECT * FROM operations WHERE id=?', (op,)).fetchone())

    def expire(self, now):
        with transaction(self.path) as db:
            rows = db.execute('SELECT id FROM operations WHERE state=? AND expires<=?', ('prepared', now)).fetchall()
            for row in rows:
                db.execute('UPDATE gifts SET reserved=NULL WHERE reserved=?', (row['id'],))
                db.execute('UPDATE operations SET state=? WHERE id=?', ('cancelled', row['id']))
            return len(rows)

    def change_asset(self, actor, ident, new_owner=None, listed=None):
        with transaction(self.path) as db:
            row = db.execute('SELECT * FROM gifts WHERE id=?', (ident,)).fetchone()
            if row is None:
                raise Rejected('unknown_input')
            self.authorize(db, actor, row['owner'])
            if row['reserved'] or row['consumed']:
                raise Rejected('asset_locked')
            if new_owner is not None:
                db.execute('UPDATE gifts SET owner=? WHERE id=?', (new_owner, ident))
            if listed is not None:
                db.execute('UPDATE gifts SET listed=? WHERE id=?', (int(listed), ident))

    def counts(self):
        with transaction(self.path) as db:
            return {'consumed': db.execute('SELECT COUNT(*) FROM gifts WHERE consumed=1').fetchone()[0],
                    'reserved': db.execute('SELECT COUNT(*) FROM gifts WHERE reserved IS NOT NULL').fetchone()[0],
                    'outputs': db.execute('SELECT COUNT(*) FROM outputs').fetchone()[0]}
