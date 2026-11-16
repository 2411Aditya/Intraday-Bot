# -*- coding: utf-8 -*-
"""Tests for the worker lock mechanism in backend/app/worker.py"""
import json
import os
import unittest
from unittest import mock

# Ensure the repository root is in sys.path for imports
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.app.worker import acquire_worker_lock, release_worker_lock, LOCK_FILE, is_pid_running

class TestWorkerLock(unittest.TestCase):
    def setUp(self):
        # Remove lock file if it exists before each test
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

    def tearDown(self):
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)

    def test_acquire_and_release(self):


        # Acquire lock should succeed first time
        acquired, reason = acquire_worker_lock()
        self.assertTrue(acquired)
        self.assertIsNone(reason)
        # Second acquisition should fail because lock exists and PID is running (mocked)
        with mock.patch('backend.app.worker.is_pid_running', return_value=True):
            acquired2, reason2 = acquire_worker_lock()
            self.assertFalse(acquired2)
            self.assertIsNotNone(reason2)
        # Release lock and ensure file removed
        release_worker_lock()
        self.assertFalse(os.path.exists(LOCK_FILE))

    def test_stale_lock_cleanup(self):
        # Simulate a stale lock file with a non‑running PID
        fake_pid = 999999
        stale_data = {"pid": fake_pid, "mode": "run-once", "started_at": "2020-01-01T00:00:00+05:30"}
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps(stale_data))
        with mock.patch('backend.app.worker.is_pid_running', return_value=False):
            # Acquisition should detect stale lock, delete it, and acquire a new lock
            acquired, reason = acquire_worker_lock()
            self.assertTrue(acquired)
            self.assertIsNone(reason)
        # Verify lock now contains current PID in JSON format
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("pid", data)
            self.assertEqual(data["pid"], os.getpid())
        

    def test_is_pid_running(self):
        # Current process PID should be reported as running
        self.assertTrue(is_pid_running(os.getpid()))
        # An unlikely high PID should be reported as not running
        self.assertFalse(is_pid_running(999999))

if __name__ == "__main__":
    unittest.main()
