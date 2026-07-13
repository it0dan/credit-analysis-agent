import os
import sys
import tempfile
import unittest

SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
sys.path.insert(0, SRC_DIR)

import db
import sse_stream


class SSEStreamTests(unittest.TestCase):
    def tearDown(self) -> None:
        for request_id in list(sse_stream._channels):
            sse_stream.close_channel(request_id)

    def test_channel_delivers_timestamped_event_and_closes(self) -> None:
        request_id = "req-live"
        sse_stream.create_channel(request_id)
        client = sse_stream.register_client(request_id)
        self.assertIsNotNone(client)
        assert client is not None

        sse_stream.emit_event(request_id, {"type": "agent_started", "request_id": request_id})
        event = client.get_nowait()

        self.assertEqual(event["type"], "agent_started")
        self.assertIn("timestamp", event)
        self.assertTrue(sse_stream.is_channel_active(request_id))

        sse_stream.close_channel(request_id)
        self.assertIsNone(client.get_nowait())
        self.assertFalse(sse_stream.is_channel_active(request_id))

    def test_full_queue_never_blocks_emitter(self) -> None:
        request_id = "req-full"
        sse_stream.create_channel(request_id)
        client = sse_stream.register_client(request_id)
        self.assertIsNotNone(client)
        assert client is not None
        for index in range(200):
            sse_stream.emit_event(request_id, {"type": "event", "index": index})

        sse_stream.emit_event(request_id, {"type": "discarded"})
        self.assertEqual(client.qsize(), 200)

    def test_closed_channel_cannot_be_recreated_by_late_client(self) -> None:
        request_id = "req-closed"
        sse_stream.create_channel(request_id)
        sse_stream.close_channel(request_id)

        self.assertIsNone(sse_stream.register_client(request_id))
        self.assertFalse(sse_stream.is_channel_active(request_id))

    def test_sse_format_uses_named_event(self) -> None:
        payload = sse_stream.format_sse({"type": "analysis_done", "status": "approved"})
        self.assertIn(b"event: analysis_done", payload)
        self.assertTrue(payload.endswith(b"\n\n"))
        self.assertEqual(sse_stream.stream_end(), b'event: stream_end\ndata: {"type":"stream_end"}\n\n')


class EventPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp_dir.name, "events.db")
        db.init_db()
        db.save_analysis({
            "request_id": "req-replay",
            "cpf_masked": "***.***.***-XX",
            "requested_amount": 1000,
            "status": "pending",
        })

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_events_are_replayed_in_emission_order(self) -> None:
        db.save_event("req-replay", {"type": "analysis_started", "timestamp": "2026-01-01T00:00:00+00:00"})
        db.save_event("req-replay", {"type": "analysis_done", "status": "approved", "timestamp": "2026-01-01T00:00:01+00:00"})

        events = db.list_events("req-replay")

        self.assertEqual([event["type"] for event in events], ["analysis_started", "analysis_done"])


if __name__ == "__main__":
    unittest.main()
