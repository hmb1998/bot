import sqlite3
from pathlib import Path

class Store:
    def __init__(self, path: Path):
        self.path = str(path)
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS settings(
                guild_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY(guild_id,key))""")
            db.execute("""CREATE TABLE IF NOT EXISTS warnings(
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
                reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("""CREATE TABLE IF NOT EXISTS xp(
                guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(guild_id,user_id))""")

    def _db(self):
        return sqlite3.connect(self.path)

    def set(self, guild_id, key, value):
        with self._db() as db:
            db.execute("INSERT INTO settings(guild_id,key,value) VALUES(?,?,?) "
                       "ON CONFLICT(guild_id,key) DO UPDATE SET value=excluded.value",
                       (guild_id, key, str(value)))

    def get(self, guild_id, key, default=None):
        with self._db() as db:
            row = db.execute("SELECT value FROM settings WHERE guild_id=? AND key=?",
                             (guild_id, key)).fetchone()
        return row[0] if row else default

    def get_bool(self, guild_id, key):
        return str(self.get(guild_id, key, "0")).lower() in {"1","true","on","yes"}

    def get_int(self, guild_id, key):
        try:
            return int(self.get(guild_id, key, "0"))
        except (TypeError, ValueError):
            return 0

    def add_warning(self, guild_id, user_id, reason):
        with self._db() as db:
            db.execute("INSERT INTO warnings(guild_id,user_id,reason) VALUES(?,?,?)",
                       (guild_id, user_id, reason))

    def warnings(self, guild_id, user_id):
        with self._db() as db:
            return db.execute("SELECT reason,created_at FROM warnings WHERE guild_id=? AND user_id=? ORDER BY rowid DESC",
                              (guild_id,user_id)).fetchall()

    def clear_warnings(self, guild_id, user_id):
        with self._db() as db:
            db.execute("DELETE FROM warnings WHERE guild_id=? AND user_id=?", (guild_id,user_id))

    def remove_last_warning(self, guild_id, user_id):
        with self._db() as db:
            row = db.execute("SELECT rowid FROM warnings WHERE guild_id=? AND user_id=? ORDER BY rowid DESC LIMIT 1",
                             (guild_id,user_id)).fetchone()
            if row:
                db.execute("DELETE FROM warnings WHERE rowid=?", (row[0],))
                return True
        return False

    def add_xp(self, guild_id, user_id, amount=1):
        with self._db() as db:
            db.execute("INSERT INTO xp(guild_id,user_id,xp) VALUES(?,?,?) "
                       "ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=xp+excluded.xp",
                       (guild_id,user_id,amount))
            return db.execute("SELECT xp FROM xp WHERE guild_id=? AND user_id=?",
                              (guild_id,user_id)).fetchone()[0]
