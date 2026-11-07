"""GPT-6.1 Terra - ROACH-2

Offline Agape room v2 prototype: inert chat data and independently pinned bundles.

V2 operation IDs are hashed into events; v1 events retain their original bytes.
V1 peers cannot process v2 bundles. Labels are unsigned and do not prove origin.

No network, model, agent execution or authentication. Transport is manual.
Run with --help; use selftest for in-memory validation.
"""
import argparse
import datetime
import hashlib
import hmac
import json
import re
import sqlite3
import sys
import unittest
from pathlib import Path

ZERO = "0" * 64
MAX_TEXT = 2048
MAX_BUNDLE = 60000
MAX_EVENTS = 512
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
HEX = re.compile(r"^[0-9a-f]{64}$")
EVENT = "agape.offline.room.event.v1"
EVENT_V2 = "agape.offline.room.event.v2"
BUNDLE = "agape.offline.room.bundle.v1"
BUNDLE_V2 = "agape.offline.room.bundle.v2"


class RoomError(Exception):
    pass


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise RoomError("invalid room or speaker")
    return value


def check_event(e, room):
    base = {"schema", "room", "speaker", "seq", "previous", "utc", "text", "id"}
    if not isinstance(e, dict):
        raise RoomError("invalid event fields")
    schema = e.get("schema")
    if schema == EVENT:
        keys = base
    elif schema == EVENT_V2:
        keys = base | {"operation_id"}
    else:
        raise RoomError("wrong event schema")
    if set(e) != keys or e["room"] != room:
        raise RoomError("invalid event fields or wrong room")
    name(e["speaker"])
    if schema == EVENT_V2:
        name(e["operation_id"])
    if type(e["seq"]) is not int or not 1 <= e["seq"] <= MAX_EVENTS:
        raise RoomError("invalid sequence")
    if not isinstance(e["previous"], str) or not HEX.fullmatch(e["previous"]):
        raise RoomError("invalid predecessor")
    if not isinstance(e["utc"], str):
        raise RoomError("invalid time")
    try:
        datetime.datetime.strptime(e["utc"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise RoomError("invalid time") from exc
    if not isinstance(e["text"], str) or not e["text"].strip() or "\x00" in e["text"]:
        raise RoomError("invalid message")
    try:
        size = len(e["text"].encode("utf-8"))
    except UnicodeError as exc:
        raise RoomError("invalid encoding") from exc
    if size > MAX_TEXT:
        raise RoomError("message too large")
    if not isinstance(e["id"], str) or not HEX.fullmatch(e["id"]):
        raise RoomError("invalid id")
    if not hmac.compare_digest(e["id"], sha(canon({k: v for k, v in e.items() if k != "id"}))):
        raise RoomError("event hash mismatch")
    return e

def init(db, room):
    name(room)
    db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.execute("""CREATE TABLE IF NOT EXISTS events
        (speaker TEXT NOT NULL, seq INTEGER NOT NULL, id TEXT NOT NULL UNIQUE,
         body BLOB NOT NULL, state TEXT NOT NULL CHECK(state IN ('LOCAL','VERIFIED')),
         PRIMARY KEY(speaker,seq))""")
    db.execute("""CREATE TABLE IF NOT EXISTS decisions
        (id TEXT PRIMARY KEY, actor TEXT NOT NULL, utc TEXT NOT NULL)""")
    row = db.execute("SELECT value FROM meta WHERE key='room'").fetchone()
    if row and row[0] != room:
        raise RoomError("wrong room")
    if not row:
        db.execute("INSERT INTO meta VALUES ('room',?)", (room,))
    db.commit()


def check_db(db, room):
    name(room)
    tables = {row[0] for row in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"meta", "events", "decisions"}.issubset(tables):
        raise RoomError("database schema missing")
    rows = db.execute("SELECT value FROM meta WHERE key='room'").fetchall()
    if rows != [(room,)]:
        raise RoomError("wrong or missing room")


def records(db, room):
    rows = db.execute("SELECT speaker,seq,id,body,state FROM events ORDER BY speaker,seq").fetchall()
    heads, operations, result = {}, set(), []
    for speaker, seq, event_id, body, state in rows:
        try:
            e = json.loads(body)
        except (ValueError, TypeError, RecursionError) as exc:
            raise RoomError("corrupt stored event") from exc
        check_event(e, room)
        prev_seq, prev_id = heads.get(speaker, (0, ZERO))
        if (e["speaker"], e["seq"], e["id"]) != (speaker, seq, event_id):
            raise RoomError("event index mismatch")
        if seq != prev_seq + 1 or e["previous"] != prev_id:
            raise RoomError("broken speaker chain")
        if e["schema"] == EVENT_V2:
            key = (speaker, e["operation_id"])
            if key in operations:
                raise RoomError("duplicate speaker operation id")
            operations.add(key)
        heads[speaker] = (seq, event_id)
        result.append((e, state))
    return result

def post(db, room, speaker, text, operation_id, now=None):
    name(speaker)
    name(operation_id)
    db.execute("BEGIN IMMEDIATE")
    try:
        old = records(db, room)
        for e, state in old:
            if (e["schema"] == EVENT_V2 and e["speaker"] == speaker
                    and e["operation_id"] == operation_id):
                if e["text"] != text:
                    raise RoomError("operation id reused with different message")
                if state != "LOCAL":
                    raise RoomError("operation id found in imported event; review required")
                db.commit()
                return {"event": e, "duplicate": True, "state": state}
        if len(old) >= MAX_EVENTS:
            raise RoomError("room full")
        prior = [e for e, _ in old if e["speaker"] == speaker]
        e = {"schema": EVENT_V2, "room": room, "speaker": speaker,
             "seq": len(prior) + 1, "previous": prior[-1]["id"] if prior else ZERO,
             "utc": now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "text": text, "operation_id": operation_id}
        e["id"] = sha(canon(e))
        check_event(e, room)
        db.execute("INSERT INTO events VALUES (?,?,?,?,?)",
                   (speaker, e["seq"], e["id"], canon(e), "LOCAL"))
        db.commit()
        return {"event": e, "duplicate": False, "state": "LOCAL"}
    except BaseException:
        db.rollback()
        raise

def export(db, room):
    events = [e for e, _ in records(db, room)]
    schema = BUNDLE_V2 if any(e["schema"] == EVENT_V2 for e in events) else BUNDLE
    raw = canon({"schema": schema, "room": room, "events": events})
    if len(raw) > MAX_BUNDLE:
        raise RoomError("bundle too large; partitioning not implemented")
    return raw

def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise RoomError("duplicate JSON key")
        out[key] = value
    return out


def _reject_constant(value):
    raise RoomError("nonfinite JSON value")


def receive(db, room, raw, expected):
    if not isinstance(expected, str) or not HEX.fullmatch(expected):
        raise RoomError("expected SHA-256 is required")
    if not isinstance(raw, bytes) or len(raw) > MAX_BUNDLE or not hmac.compare_digest(sha(raw), expected):
        raise RoomError("bundle hash mismatch or size limit")
    try:
        b = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                       parse_constant=_reject_constant)
        if (not isinstance(b, dict) or set(b) != {"schema", "room", "events"}
                or b["schema"] not in (BUNDLE, BUNDLE_V2) or b["room"] != room
                or not isinstance(b["events"], list) or len(b["events"]) > MAX_EVENTS):
            raise RoomError("invalid bundle")
        if canon(b) != raw:
            raise RoomError("bundle is not canonical")
        incoming = sorted([check_event(e, room) for e in b["events"]],
                          key=lambda e: (e["speaker"], e["seq"]))
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise RoomError("invalid bundle") from exc
    if b["schema"] == BUNDLE and any(e["schema"] == EVENT_V2 for e in incoming):
        raise RoomError("v2 event in v1 bundle")
    db.execute("BEGIN IMMEDIATE")
    try:
        old = records(db, room)
        heads, seen, operations, pending, duplicates = {}, {}, {}, [], 0
        for e, _ in old:
            heads[e["speaker"]] = (e["seq"], e["id"])
            seen[(e["speaker"], e["seq"])] = e["id"]
            if e["schema"] == EVENT_V2:
                operations[(e["speaker"], e["operation_id"])] = e["id"]
        for e in incoming:
            key = (e["speaker"], e["seq"])
            if key in seen:
                if seen[key] != e["id"]:
                    raise RoomError("speaker sequence conflict")
                duplicates += 1
                continue
            if e["schema"] == EVENT_V2:
                op_key = (e["speaker"], e["operation_id"])
                if op_key in operations:
                    raise RoomError("speaker operation id conflict")
                operations[op_key] = e["id"]
            prev_seq, prev_id = heads.get(e["speaker"], (0, ZERO))
            if e["seq"] != prev_seq + 1 or e["previous"] != prev_id:
                raise RoomError("missing predecessor")
            pending.append(e)
            heads[e["speaker"]] = (e["seq"], e["id"])
            seen[key] = e["id"]
        if len(old) + len(pending) > MAX_EVENTS:
            raise RoomError("room full")
        for e in pending:
            db.execute("INSERT INTO events VALUES (?,?,?,?,?)",
                       (e["speaker"], e["seq"], e["id"], canon(e), "VERIFIED"))
        db.commit()
        return {"added": len(pending), "duplicates": duplicates, "bundle_sha256": sha(raw),
                "identity": "UNVERIFIED"}
    except BaseException:
        db.rollback()
        raise

def admit(db, room, event_id, actor):
    name(actor)
    if not isinstance(event_id, str) or not HEX.fullmatch(event_id):
        raise RoomError("invalid id")
    db.execute("BEGIN IMMEDIATE")
    try:
        records(db, room)
        row = db.execute("SELECT state FROM events WHERE id=?", (event_id,)).fetchone()
        if not row or row[0] != "VERIFIED":
            raise RoomError("requires an imported verified message")
        old = db.execute("SELECT actor,utc FROM decisions WHERE id=?", (event_id,)).fetchone()
        if old:
            if old[0] != actor:
                raise RoomError("admission already recorded for a different actor")
            db.commit()
            return {"id": event_id, "actor": old[0], "utc": old[1], "duplicate": True}
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute("INSERT INTO decisions VALUES (?,?,?)", (event_id, actor, now))
        db.commit()
        return {"id": event_id, "actor": actor, "utc": now, "duplicate": False}
    except BaseException:
        db.rollback()
        raise

class Tests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
        init(self.a, "room")
        init(self.b, "room")

    def tearDown(self):
        self.a.close()
        self.b.close()

    def transfer(self):
        raw = export(self.a, "room")
        return receive(self.b, "room", raw, sha(raw))

    def test_exact_retry_and_conflict(self):
        first = post(self.a, "room", "A", "hello", "op-1", "2026-01-01T00:00:00Z")
        retry = post(self.a, "room", "A", "hello", "op-1", "2026-01-02T00:00:00Z")
        self.assertEqual(first["event"], retry["event"])
        self.assertTrue(retry["duplicate"])
        with self.assertRaises(RoomError):
            post(self.a, "room", "A", "different", "op-1")
        self.assertEqual(len(records(self.a, "room")), 1)
        second = post(self.a, "room", "A", "hello", "op-2")
        self.assertNotEqual(first["event"]["id"], second["event"]["id"])

    def test_restored_sqlite_bytes_preserve_operation(self):
        first = post(self.a, "room", "A", "hello", "op-1")
        image = self.a.serialize()
        restored = sqlite3.connect(":memory:")
        try:
            restored.deserialize(image)
            check_db(restored, "room")
            retry = post(restored, "room", "A", "hello", "op-1")
            self.assertEqual(retry["event"], first["event"])
            self.assertTrue(retry["duplicate"])
        finally:
            restored.close()

    def test_imported_operation_refused_as_local(self):
        post(self.a, "room", "A", "hello", "op-1")
        self.assertEqual(self.transfer()["added"], 1)
        with self.assertRaises(RoomError):
            post(self.b, "room", "A", "hello", "op-1")
        self.assertEqual(len(records(self.b, "room")), 1)
        self.assertEqual(self.transfer()["duplicates"], 1)

    def test_v1_bytes_preserved_and_v2_bundle_versioned(self):
        old = {"schema": EVENT, "room": "room", "speaker": "A", "seq": 1,
               "previous": ZERO, "utc": "2026-01-01T00:00:00Z", "text": "legacy"}
        old["id"] = sha(canon(old))
        old_raw = canon({"schema": BUNDLE, "room": "room", "events": [old]})
        self.assertEqual(receive(self.a, "room", old_raw, sha(old_raw))["added"], 1)
        self.assertEqual(export(self.a, "room"), old_raw)
        post(self.a, "room", "B", "new", "op-1")
        newer = export(self.a, "room")
        self.assertEqual(json.loads(newer)["schema"], BUNDLE_V2)
        self.assertEqual(receive(self.b, "room", newer, sha(newer))["added"], 2)
        self.assertEqual(canon(records(self.b, "room")[0][0]), canon(old))

    def test_actor_conflict_and_unchanged_admission(self):
        event = post(self.a, "room", "A", "hello", "op-1")["event"]
        self.transfer()
        first = admit(self.b, "room", event["id"], "operator")
        again = admit(self.b, "room", event["id"], "operator")
        self.assertEqual(first["utc"], again["utc"])
        self.assertTrue(again["duplicate"])
        with self.assertRaises(RoomError):
            admit(self.b, "room", event["id"], "other")
        self.assertEqual(self.b.execute("SELECT count(*) FROM decisions").fetchone()[0], 1)

    def test_invalid_and_noncanonical_rejected_before_write(self):
        samples = [b'{"schema":NaN}', b'{"x":1,"x":1}',
                   b'[' * 1200 + b']' * 1200, b'\xff']
        for raw in samples:
            with self.subTest(raw=raw[:20]):
                with self.assertRaises(RoomError):
                    receive(self.b, "room", raw, sha(raw))
        self.assertEqual(records(self.b, "room"), [])

    def test_fork_and_tamper_preserve_existing(self):
        post(self.a, "room", "A", "one", "op-1", "2026-01-01T00:00:00Z")
        post(self.b, "room", "A", "two", "op-2", "2026-01-01T00:00:00Z")
        raw = export(self.a, "room")
        with self.assertRaises(RoomError):
            receive(self.b, "room", raw + b" ", sha(raw))
        with self.assertRaises(RoomError):
            receive(self.b, "room", raw, sha(raw))
        self.assertEqual(len(records(self.b, "room")), 1)

    def test_incomplete_bundle_is_atomic(self):
        post(self.a, "room", "A", "one", "op-1")
        post(self.a, "room", "A", "two", "op-2")
        b = json.loads(export(self.a, "room"))
        b["events"] = b["events"][1:]
        raw = canon(b)
        with self.assertRaises(RoomError):
            receive(self.b, "room", raw, sha(raw))
        self.assertEqual(records(self.b, "room"), [])

    def test_quota_still_allows_existing_retry(self):
        global MAX_EVENTS
        saved = MAX_EVENTS
        MAX_EVENTS = 1
        try:
            first = post(self.a, "room", "A", "hello", "op-1")
            self.assertTrue(post(self.a, "room", "A", "hello", "op-1")["duplicate"])
            with self.assertRaises(RoomError):
                post(self.a, "room", "A", "two", "op-2")
            self.assertEqual(len(records(self.a, "room")), 1)
        finally:
            MAX_EVENTS = saved

    def test_insert_failure_rolls_back_and_unlocks(self):
        self.a.execute("CREATE TRIGGER test_failure BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'test'); END")
        self.a.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            post(self.a, "room", "A", "hello", "op-1")
        self.assertFalse(self.a.in_transaction)
        self.assertEqual(records(self.a, "room"), [])
        self.a.execute("DROP TRIGGER test_failure")
        self.a.commit()
        self.assertFalse(post(self.a, "room", "A", "hello", "op-1")["duplicate"])

    def test_lock_prevents_overlapping_writer(self):
        uri = "file:room_shared_test?mode=memory&cache=shared"
        a = sqlite3.connect(uri, uri=True, timeout=0.01)
        b = sqlite3.connect(uri, uri=True, timeout=0.01)
        try:
            init(a, "room")
            check_db(b, "room")
            a.execute("BEGIN IMMEDIATE")
            with self.assertRaises(sqlite3.OperationalError):
                post(b, "room", "A", "hello", "op-1")
            a.rollback()
            post(b, "room", "A", "hello", "op-1")
            self.assertTrue(post(a, "room", "A", "hello", "op-1")["duplicate"])
            self.assertEqual(len(records(a, "room")), 1)
        finally:
            a.close()
            b.close()

    def test_wrong_schema_and_size(self):
        with self.assertRaises(RoomError):
            post(self.a, "room", "A", "x" * (MAX_TEXT + 1), "op-1")
        post(self.a, "room", "A", "hello", "op-1")
        data = json.loads(export(self.a, "room"))
        data["schema"] = BUNDLE
        raw = canon(data)
        with self.assertRaises(RoomError):
            receive(self.b, "room", raw, sha(raw))
        self.assertEqual(records(self.b, "room"), [])

    def test_schema_check_does_not_initialize(self):
        empty = sqlite3.connect(":memory:")
        try:
            with self.assertRaises(RoomError):
                check_db(empty, "room")
            self.assertEqual(empty.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall(), [])
        finally:
            empty.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    for cmd in ("init", "post", "export", "import", "list", "search", "admit", "verify"):
        q = sub.add_parser(cmd)
        q.add_argument("--db", required=True)
        q.add_argument("--room", required=True)
        if cmd == "post":
            q.add_argument("--speaker", required=True)
            q.add_argument("--text", required=True)
            q.add_argument("--operation-id", required=True,
                           help="Caller-generated stable ID saved before first attempt")
        if cmd == "import":
            q.add_argument("--file", required=True)
            q.add_argument("--expected", required=True)
        if cmd == "search":
            q.add_argument("--query", required=True)
        if cmd == "admit":
            q.add_argument("--id", required=True)
            q.add_argument("--actor", required=True)
    a = p.parse_args()
    if a.cmd == "selftest":
        return 0 if unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Tests)).wasSuccessful() else 1
    if a.db == ":memory:":
        raise RoomError("memory database reserved for selftest")
    path = Path(a.db).expanduser().absolute()
    if any(x.is_symlink() for x in [path, *path.parents]):
        raise RoomError("symlink paths are not supported")
    if a.cmd == "init" and path.exists():
        raise RoomError("database already exists")
    if a.cmd != "init" and not path.is_file():
        raise RoomError("database missing")
    db = sqlite3.connect(str(path), timeout=5)
    try:
        if a.cmd == "init":
            init(db, a.room)
        else:
            if a.cmd in ("list", "search", "verify", "export"):
                db.execute("PRAGMA query_only=ON")
            check_db(db, a.room)
        if a.cmd == "post":
            result = post(db, a.room, a.speaker, a.text, a.operation_id)
        elif a.cmd == "import":
            with open(a.file, "rb") as f:
                raw = f.read(MAX_BUNDLE + 1)
            result = receive(db, a.room, raw, a.expected)
        elif a.cmd == "export":
            sys.stdout.buffer.write(export(db, a.room))
            return 0
        elif a.cmd == "admit":
            result = admit(db, a.room, a.id, a.actor)
        elif a.cmd in ("list", "search"):
            query = a.query.casefold() if a.cmd == "search" else ""
            result = [{"event": e, "state": state, "identity": "UNVERIFIED",
                       "admitted": bool(db.execute("SELECT 1 FROM decisions WHERE id=?", (e["id"],)).fetchone())}
                      for e, state in records(db, a.room) if query in e["text"].casefold()]
        elif a.cmd == "verify":
            event_count = len(records(db, a.room))
            integrity = [row[0] for row in db.execute("PRAGMA integrity_check")]
            if integrity != ["ok"]:
                raise RoomError("database integrity check failed")
            result = {"events": event_count, "integrity": "ok",
                      "identity": "UNVERIFIED",
                      "scope": "Event hashes, speaker chains and SQLite structure; local states and decisions are not tamper-evident."}
        else:
            result = {"room": a.room, "status": "initialized"}
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RoomError, OSError, sqlite3.Error) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        sys.exit(1)

