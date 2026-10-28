"""Offline proposal model. Not Telegram code, an API client, or a TON contract."""
import sqlite3
import uuid
from contextlib import contextmanager


class Rejected(Exception):
    pass


class ReferenceService:
    def __init__(self, path):
        self.path = str(path)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS gifts (
                    id TEXT PRIMARY KEY, owner TEXT, custody TEXT,
                    ever_exported INTEGER, details INTEGER, live INTEGER,
                    revision INTEGER);
                CREATE TABLE IF NOT EXISTS grants (actor TEXT, owner TEXT,
                    PRIMARY KEY(actor, owner));
                CREATE TABLE IF NOT EXISTS balances (actor TEXT PRIMARY KEY,
                    stars INTEGER CHECK(stars >= 0));
                CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY,
                    fee INTEGER, revision INTEGER);
                INSERT OR IGNORE INTO config VALUES(1, 25, 1);
                CREATE TABLE IF NOT EXISTS quotes (id TEXT PRIMARY KEY,
                    actor TEXT, gift TEXT, owner TEXT, revision INTEGER,
                    fee INTEGER, fee_revision INTEGER, expires INTEGER);
                CREATE TABLE IF NOT EXISTS receipts (operation TEXT PRIMARY KEY,
                    actor TEXT, gift TEXT, quote TEXT, paid INTEGER);
                CREATE TABLE IF NOT EXISTS removed_details (
                    gift TEXT PRIMARY KEY, operation TEXT);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def checked_gift(db, actor, gift_id):
        gift = db.execute('SELECT * FROM gifts WHERE id=?', (gift_id,)).fetchone()
        if gift is None:
            raise Rejected('not_found')
        permitted = gift['owner'] == actor or db.execute(
            'SELECT 1 FROM grants WHERE actor=? AND owner=?',
            (actor, gift['owner'])).fetchone()
        if not permitted:
            raise Rejected('not_owner_or_authorized_manager')
        if not gift['live']:
            raise Rejected('gift_unavailable')
        if gift['custody'] != 'telegram':
            raise Rejected('supported_return_or_wallet_flow_required')
        removed = db.execute('SELECT 1 FROM removed_details WHERE gift=?',
                             (gift_id,)).fetchone()
        if not gift['details'] or removed:
            raise Rejected('already_removed')
        return gift

    def apply_authoritative_snapshot(self, gift_id, *, owner, custody,
                                     ever_exported, details, live=True):
        """Synthetic trusted import feed, not a user-facing mutation endpoint."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM gifts WHERE id=?', (gift_id,)).fetchone()
            removed = db.execute('SELECT 1 FROM removed_details WHERE gift=?',
                                 (gift_id,)).fetchone()
            exported = bool(ever_exported or (old and old['ever_exported']))
            revision = old['revision'] + 1 if old else 1
            db.execute('INSERT INTO gifts VALUES(?,?,?,?,?,?,?) '
                       'ON CONFLICT(id) DO UPDATE SET owner=excluded.owner, '
                       'custody=excluded.custody, ever_exported=excluded.ever_exported, '
                       'details=excluded.details, live=excluded.live, '
                       'revision=excluded.revision',
                       (gift_id, owner, custody, int(exported),
                        int(bool(details) and not removed), int(bool(live)), revision))

    def quote(self, actor, gift_id, now=0):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            gift = self.checked_gift(db, actor, gift_id)
            config = db.execute('SELECT * FROM config WHERE id=1').fetchone()
            if not isinstance(config['fee'], int) or config['fee'] <= 0:
                raise Rejected('invalid_fee_configuration')
            quote_id = uuid.uuid4().hex
            db.execute('INSERT INTO quotes VALUES(?,?,?,?,?,?,?,?)', (
                quote_id, actor, gift_id, gift['owner'], gift['revision'],
                config['fee'], config['revision'], now + 300))
            return quote_id

    def pay(self, actor, gift_id, quote_id, operation, *, confirmed,
            now=1, fail_at=None):
        if not operation:
            raise Rejected('operation_required')
        if confirmed is not True:
            raise Rejected('confirmation_required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            receipt = db.execute('SELECT * FROM receipts WHERE operation=?',
                                 (operation,)).fetchone()
            if receipt:
                if (receipt['actor'], receipt['gift'], receipt['quote']) != (
                        actor, gift_id, quote_id):
                    raise Rejected('operation_binding_conflict')
                return dict(receipt)
            quote = db.execute('SELECT * FROM quotes WHERE id=?',
                               (quote_id,)).fetchone()
            if quote is None or (quote['actor'], quote['gift']) != (actor, gift_id):
                raise Rejected('invalid_quote')
            if now >= quote['expires']:
                raise Rejected('quote_expired')
            gift = self.checked_gift(db, actor, gift_id)
            if (gift['owner'], gift['revision']) != (
                    quote['owner'], quote['revision']):
                raise Rejected('gift_changed')
            config = db.execute('SELECT * FROM config WHERE id=1').fetchone()
            if (config['fee'], config['revision']) != (
                    quote['fee'], quote['fee_revision']):
                raise Rejected('price_changed_reconfirm')
            debit = db.execute('UPDATE balances SET stars=stars-? '
                               'WHERE actor=? AND stars>=?',
                               (quote['fee'], actor, quote['fee']))
            if debit.rowcount != 1:
                raise Rejected('balance_insufficient')
            if fail_at == 'after_debit':
                raise RuntimeError('simulated pre-commit failure')
            db.execute('UPDATE gifts SET details=0, revision=revision+1 WHERE id=?',
                       (gift_id,))
            if fail_at == 'after_removal':
                raise RuntimeError('simulated pre-commit failure')
            db.execute('INSERT INTO removed_details VALUES(?,?)',
                       (gift_id, operation))
            if fail_at == 'after_marker':
                raise RuntimeError('simulated pre-commit failure')
            db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',
                       (operation, actor, gift_id, quote_id, quote['fee']))
            if fail_at == 'after_receipt':
                raise RuntimeError('simulated pre-commit failure')
            return dict(db.execute('SELECT * FROM receipts WHERE operation=?',
                                   (operation,)).fetchone())
