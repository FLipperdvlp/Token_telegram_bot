import hashlib
import hmac
from datetime import datetime, timezone
import aiosqlite
from contextlib import asynccontextmanager

SCHEMA = '''
CREATE TABLE IF NOT EXISTS tokens (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 token_hash TEXT NOT NULL UNIQUE,
 token_value TEXT NOT NULL,
 phone TEXT,
 status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available','issued','invalid')),
 created_at TEXT NOT NULL,
 issued_at TEXT
);
CREATE TABLE IF NOT EXISTS issues (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 token_id INTEGER NOT NULL UNIQUE REFERENCES tokens(id),
 user_id INTEGER NOT NULL,
 username TEXT,
 full_name TEXT,
 chat_id INTEGER NOT NULL,
 issued_at TEXT NOT NULL,
 verdict TEXT CHECK(verdict IN ('ok','fail') OR verdict IS NULL),
 voted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tokens_status ON tokens(status);
CREATE INDEX IF NOT EXISTS idx_issues_user ON issues(user_id);
'''

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

class Store:
    def __init__(self, path):
        self.path = path

    @asynccontextmanager
    async def connect(self):
        async with aiosqlite.connect(self.path, timeout=30) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute('PRAGMA foreign_keys=ON')
            await conn.execute('PRAGMA busy_timeout=30000')
            yield conn

    async def initialize(self):
        async with self.connect() as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.executescript(SCHEMA)
            await db.commit()

    async def import_rows(self, rows):
        added = duplicates = 0
        async with self.connect() as db:
            await db.execute('BEGIN IMMEDIATE')
            try:
                for phone, value in rows:
                    digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
                    cur = await db.execute('INSERT OR IGNORE INTO tokens(token_hash,token_value,phone,created_at) VALUES(?,?,?,?)', (digest, value, phone, now()))
                    if cur.rowcount: added += 1
                    else: duplicates += 1
                await db.commit()
            except BaseException:
                await db.rollback()
                raise
        return added, duplicates

    async def claim(self, user, chat_id):
        async with self.connect() as db:
            await db.execute('BEGIN IMMEDIATE')
            try:
                # One outstanding issue per user. Historical issues remain visible.
                cur = await db.execute('SELECT i.id, i.verdict FROM issues i WHERE i.user_id=? ORDER BY i.id DESC LIMIT 1', (user.id,))
                previous = await cur.fetchone()
                if previous and previous['verdict'] is None:
                    await db.commit()
                    return 'pending', dict(previous)
                cur = await db.execute("SELECT id, token_value, phone FROM tokens WHERE status='available' ORDER BY id LIMIT 1")
                token = await cur.fetchone()
                if token is None:
                    await db.commit()
                    return 'empty', None
                await db.execute("UPDATE tokens SET status='issued', issued_at=? WHERE id=? AND status='available'", (now(), token['id']))
                cur = await db.execute('INSERT INTO issues(token_id,user_id,username,full_name,chat_id,issued_at) VALUES(?,?,?,?,?,?)', (token['id'],user.id,user.username or '',user.full_name,chat_id,now()))
                issue_id = cur.lastrowid
                await db.commit()
                return 'issued', {'issue_id': issue_id, 'token': token['token_value'], 'phone': token['phone']}
            except BaseException:
                await db.rollback()
                raise

    async def vote(self, issue_id, user_id, verdict):
        async with self.connect() as db:
            await db.execute('BEGIN IMMEDIATE')
            try:
                cur = await db.execute('SELECT user_id, verdict FROM issues WHERE id=?', (issue_id,))
                issue = await cur.fetchone()
                if not issue:
                    result = 'missing'
                elif issue['user_id'] != user_id:
                    result = 'forbidden'
                elif issue['verdict'] is not None:
                    result = 'already'
                else:
                    await db.execute('UPDATE issues SET verdict=?, voted_at=? WHERE id=? AND verdict IS NULL', (verdict, now(), issue_id))
                    result = 'saved'
                await db.commit()
                return result
            except BaseException:
                await db.rollback()
                raise

    async def issue_data(self, issue_id, user_id):
        async with self.connect() as db:
            cur = await db.execute(
                '''SELECT i.id AS issue_id, i.chat_id, t.token_value AS token, t.phone
                FROM issues i JOIN tokens t ON t.id=i.token_id
                WHERE i.id=? AND i.user_id=?''',
                (issue_id, user_id)
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def latest_issue(self, user_id):
        async with self.connect() as db:
            cur = await db.execute(
                '''SELECT i.id, i.chat_id, t.token_value, t.phone
                FROM issues i JOIN tokens t ON t.id=i.token_id
                WHERE i.user_id=? ORDER BY i.id DESC LIMIT 1''',
                (user_id,)
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def stats(self):
        async with self.connect() as db:
            cur = await db.execute('''SELECT (SELECT COUNT(*) FROM tokens) total,
            (SELECT COUNT(*) FROM tokens WHERE status='available') available,
            (SELECT COUNT(*) FROM tokens WHERE status='invalid') invalid,
            (SELECT COUNT(*) FROM issues) issued,
            (SELECT COUNT(*) FROM issues WHERE verdict='ok') ok,
            (SELECT COUNT(*) FROM issues WHERE verdict='fail') fail,
            (SELECT COUNT(*) FROM issues WHERE verdict IS NULL) pending''')
            return dict(await cur.fetchone())

    async def profile(self, uid):
        async with self.connect() as db:
            cur = await db.execute('SELECT COUNT(*) total, COALESCE(SUM(verdict=\'ok\'),0) ok, COALESCE(SUM(verdict=\'fail\'),0) fail, COALESCE(SUM(verdict IS NULL),0) pending FROM issues WHERE user_id=?', (uid,))
            return dict(await cur.fetchone())

    async def history(self, limit=20):
        async with self.connect() as db:
            cur = await db.execute('SELECT id, user_id, username, issued_at, verdict FROM issues ORDER BY id DESC LIMIT ?', (limit,))
            return [dict(r) for r in await cur.fetchall()]

    async def delete_available(self, token_id):
        async with self.connect() as db:
            cur = await db.execute("UPDATE tokens SET status='invalid', token_value='' WHERE id=? AND status='available'", (token_id,))
            await db.commit()
            return cur.rowcount > 0
