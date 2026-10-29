#!/usr/bin/env python3
"""Unit tests for the deterministic Jira REST client."""

import errno
import http.client
import importlib.util
import io
import json
import os
import socket
import ssl
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "jira_search.py"
SPEC = importlib.util.spec_from_file_location("jira_search_under_test", SCRIPT)
jira_search = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jira_search)


class Response:
    def __init__(self, data):
        self.data = data
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        return False

    def read(self):
        if isinstance(self.data, Exception):
            raise self.data
        if isinstance(self.data, bytes):
            return self.data
        return json.dumps(self.data).encode()


class JiraSearchClientTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(
            os.environ, {"JIRA_USERNAME": "user", "JIRA_API_TOKEN": "token"})
        self.env.start()
        self.addCleanup(self.env.stop)
        sleep_patcher = mock.patch.object(jira_search.time, "sleep")
        self.sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        network_patcher = mock.patch.object(
            jira_search.urllib.request, "urlopen",
            side_effect=AssertionError("Unexpected network request"))
        self.network = network_patcher.start()
        self.addCleanup(network_patcher.stop)

    def test_missing_credentials_fails(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(jira_search.JiraSearchError):
                jira_search.search("project = USHIFT")

    def test_empty_success_is_empty_list(self):
        with mock.patch.object(jira_search.urllib.request, "urlopen",
                               return_value=Response({"issues": []})):
            self.assertEqual(jira_search.search("project = USHIFT"), [])

    def test_http_failure_is_not_empty_success(self):
        error = urllib.error.HTTPError("url", 503, "unavailable", {}, None)
        with mock.patch.object(jira_search.urllib.request, "urlopen",
                               side_effect=error):
            with self.assertRaises(jira_search.JiraSearchError):
                jira_search.search("project = USHIFT")

    def test_transport_recovery(self):
        errors = [
            ConnectionResetError(errno.ECONNRESET, "private error"),
            ConnectionAbortedError(errno.ECONNABORTED, "private abort"),
            ConnectionRefusedError(errno.ECONNREFUSED, "private refusal"),
            OSError(errno.ETIMEDOUT, "private timeout"),
            BrokenPipeError(errno.EPIPE, "private pipe"),
            TimeoutError("private timeout"),
            urllib.error.URLError(TimeoutError("private timeout")),
            urllib.error.URLError(ConnectionResetError(errno.ECONNRESET, "private")),
            socket.gaierror(socket.EAI_AGAIN, "temporary DNS failure"),
            http.client.RemoteDisconnected("connection closed"),
            http.client.IncompleteRead(b"private response", 100),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.sleep.reset_mock()
                response = Response({"issues": [{"key": "USHIFT-1"}]})
                with mock.patch.object(jira_search.urllib.request, "urlopen",
                                       side_effect=[error, response]) as network:
                    self.assertEqual(jira_search.search("private JQL"),
                                     [{"key": "USHIFT-1"}])
                self.assertEqual(network.call_count, 2)
                self.sleep.assert_called_once_with(1)
                self.assertTrue(response.closed)

    def test_transport_exhaustion_is_bounded_and_safe(self):
        error = ConnectionResetError(errno.ECONNRESET, "private JQL token response")
        with (
            mock.patch.object(jira_search.urllib.request, "urlopen",
                              side_effect=error) as network,
            mock.patch("sys.stderr", new_callable=io.StringIO) as diagnostics,
            self.assertRaisesRegex(jira_search.JiraSearchError, "after 3 attempts") as raised,
        ):
            jira_search.search("private JQL")
        self.assertEqual(network.call_count, 3)
        self.assertEqual(self.sleep.call_args_list, [mock.call(1), mock.call(2)])
        self.assertIs(raised.exception.__cause__, error)
        self.assertNotIn("private", str(raised.exception) + diagnostics.getvalue())
        self.assertIn("attempt 1/3", diagnostics.getvalue())
        self.assertIn("attempt 2/3", diagnostics.getvalue())

    def test_http_errors_are_immediate_and_closed(self):
        for status in (400, 401, 403, 404, 429, 500, 502, 503, 504):
            with self.subTest(status=status):
                body = io.BytesIO(b"private response")
                error = urllib.error.HTTPError("private URL", status, "private reason",
                                               {"Retry-After": "999999"}, body)
                with (
                    mock.patch.object(jira_search.urllib.request, "urlopen",
                                      side_effect=error) as network,
                    self.assertRaisesRegex(jira_search.JiraSearchError, f"^Jira HTTP {status}$"),
                ):
                    jira_search.search("private JQL")
                self.assertEqual(network.call_count, 1)
                self.sleep.assert_not_called()
                self.assertTrue(body.closed)

    def test_permanent_transport_errors_are_immediate(self):
        errors = [
            urllib.error.URLError("private reason"),
            urllib.error.URLError(ssl.SSLCertVerificationError("private certificate")),
            socket.gaierror(socket.EAI_NONAME, "unknown hostname"),
            PermissionError(errno.EACCES, "private file"),
        ]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with (
                    mock.patch.object(jira_search.urllib.request, "urlopen",
                                      side_effect=error) as network,
                    self.assertRaisesRegex(jira_search.JiraSearchError,
                                           "^Jira non-retryable transport error$"),
                ):
                    jira_search.search("private JQL")
                self.assertEqual(network.call_count, 1)
                self.sleep.assert_not_called()

    def test_invalid_payloads_are_immediate_and_closed(self):
        for body in (b"private invalid JSON", b"\xff", [], {}, {"issues": "invalid"}):
            with self.subTest(body=body):
                response = Response(body)
                with (
                    mock.patch.object(jira_search.urllib.request, "urlopen",
                                      return_value=response) as network,
                    self.assertRaises(jira_search.JiraSearchError) as raised,
                ):
                    jira_search.search("private JQL")
                self.assertNotIn("private", str(raised.exception))
                self.assertEqual(network.call_count, 1)
                self.sleep.assert_not_called()
                self.assertTrue(response.closed)

    def test_read_failure_closes_response_before_retry(self):
        failed = Response(ConnectionResetError(errno.ECONNRESET, "reset"))
        success = Response({"issues": []})

        def sleep(delay):
            self.assertTrue(failed.closed)

        self.sleep.side_effect = sleep
        with mock.patch.object(jira_search.urllib.request, "urlopen",
                               side_effect=[failed, success]):
            self.assertEqual(jira_search.search("project = USHIFT"), [])
        self.assertTrue(success.closed)

    def test_retry_preserves_paginated_post_payload_and_auth(self):
        first = Response({"issues": [{"key": "USHIFT-1"}], "isLast": False,
                          "nextPageToken": "next"})
        second = Response({"issues": [{"key": "USHIFT-2"}], "isLast": True})
        reset = ConnectionResetError(errno.ECONNRESET, "reset")
        with mock.patch.object(jira_search.urllib.request, "urlopen",
                               side_effect=[reset, reset, first, reset, reset, second]) as network:
            issues = jira_search.search_all("project = USHIFT", fields="summary,status",
                                           page_size=7)
        self.assertEqual([issue["key"] for issue in issues], ["USHIFT-1", "USHIFT-2"])
        self.assertEqual(self.sleep.call_args_list,
                         [mock.call(1), mock.call(2), mock.call(1), mock.call(2)])
        for index, call in enumerate(network.call_args_list):
            request = call.args[0]
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.full_url, f"{jira_search._JIRA_API}/search/jql")
            self.assertEqual(request.get_header("Authorization"), "Basic dXNlcjp0b2tlbg==")
            self.assertEqual(request.get_header("Content-type"), "application/json")
            self.assertEqual(request.get_header("Accept"), "application/json")
            expected = {"jql": "project = USHIFT", "fields": ["summary", "status"],
                        "maxResults": 7}
            if index >= 3:
                expected["nextPageToken"] = "next"
            self.assertEqual(json.loads(request.data), expected)
            self.assertEqual(call.kwargs, {"timeout": 30})
        self.assertIs(network.call_args_list[0].args[0], network.call_args_list[2].args[0])
        self.assertIs(network.call_args_list[3].args[0], network.call_args_list[5].args[0])

    def test_later_page_exhaustion_does_not_return_partial_results(self):
        first = Response({"issues": [{"key": "USHIFT-1"}], "isLast": False,
                          "nextPageToken": "next"})
        reset = TimeoutError("private timeout")
        with (
            mock.patch.object(jira_search.urllib.request, "urlopen",
                              side_effect=[first, reset, reset, reset]) as network,
            self.assertRaisesRegex(jira_search.JiraSearchError, "after 3 attempts"),
        ):
            jira_search.search_all("project = USHIFT")
        self.assertEqual(network.call_count, 4)
        self.assertTrue(first.closed)

    def test_search_all_paginates_with_next_page_token(self):
        pages = [
            Response({"issues": [{"key": "USHIFT-1"}], "isLast": False,
                      "nextPageToken": "next"}),
            Response({"issues": [{"key": "USHIFT-2"}], "isLast": True}),
        ]
        requests = []

        def urlopen(request, timeout):
            requests.append(json.loads(request.data))
            return pages.pop(0)

        with mock.patch.object(jira_search.urllib.request, "urlopen",
                               side_effect=urlopen):
            issues = jira_search.search_all("project = USHIFT")
        self.assertEqual([issue["key"] for issue in issues],
                         ["USHIFT-1", "USHIFT-2"])
        self.assertNotIn("nextPageToken", requests[0])
        self.assertEqual(requests[1]["nextPageToken"], "next")

    def test_search_all_rejects_repeated_token(self):
        response = Response({"issues": [], "isLast": False,
                             "nextPageToken": "same"})
        with mock.patch.object(jira_search.urllib.request, "urlopen",
                               return_value=response):
            with self.assertRaisesRegex(jira_search.JiraSearchError, "repeated"):
                jira_search.search_all("project = USHIFT")

    def test_search_all_rejects_incomplete_page(self):
        response = Response({"issues": [], "isLast": False})
        with mock.patch.object(jira_search.urllib.request, "urlopen",
                               return_value=response):
            with self.assertRaisesRegex(jira_search.JiraSearchError,
                                        "missing nextPageToken"):
                jira_search.search_all("project = USHIFT")


if __name__ == "__main__":
    unittest.main()
