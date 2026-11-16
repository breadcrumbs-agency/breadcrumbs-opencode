"""The ACE bridge of OpenCode: a request passes as it is under the target, a long one folds into a layer of crumbs with its
newest turns exact, the layer is the compaction summary, and each request writes one line to ace.log. The messages are
the openai-shaped ones that plugin/convert.js makes. Run with breadcrumbs-common and this folder on PYTHONPATH."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from breadcrumbs_opencode import ace


def chat(turns, size=1200):
    out = [{"role": "system", "content": "You are a coding agent."}]
    for n in range(turns):
        text = ("note %d: " % n) + ("kettle water green tea steep minutes temperature " * (size // 48))
        out.append({"role": "user", "content": text})
        out.append({"role": "assistant", "content": "answer %d about the kettle and the tea." % n})
    return out


class Bridge(unittest.TestCase):
    def setUp(self):
        # Not under the system temp folder: scope.py treats /tmp and /var/folders as no project (sync.TEMP).
        parent = os.path.join(os.path.expanduser("~"), ".cache", "breadcrumbs-opencode-tests")
        os.makedirs(parent, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        self.base = os.path.join(tmp.name, "opencode", "breadcrumbs")  # the default memory: its last folder is breadcrumbs
        self.cwd = os.path.join(tmp.name, "nowhere")  # no project here: the default memory
        os.makedirs(self.cwd)
        os.makedirs(self.base)
        env = mock.patch.dict(os.environ, {"BREADCRUMBS_HOME": self.base, "BREADCRUMBS_ACE_TOKENS": "2000",
                                           "BREADCRUMBS_SCOPE": "auto"})
        env.start()
        self.addCleanup(env.stop)

    def engine(self, window=4000):
        root = ace.home(self.cwd)
        return ace.Ace(root, "ses_1", "demo-model", window)

    def test_a_short_request_passes(self):
        engine = self.engine(window=200_000)
        try:
            self.assertIsNone(ace.select(engine, chat(2)))
        finally:
            engine.close_all()

    def test_a_long_request_folds_and_keeps_the_newest_turns_exact(self):
        messages = chat(60)
        engine = self.engine(window=4000)
        try:
            out = ace.select(engine, messages)
        finally:
            engine.close_all()
        self.assertIsNotNone(out)
        news = [item["new"] for item in out if "new" in item]
        kept = [item["i"] for item in out if "i" in item]
        self.assertTrue(news, "the layer is a new message")
        self.assertIn("crumb", news[0]["content"] if isinstance(news[0]["content"], str) else "")
        self.assertEqual(kept[-1], len(messages) - 1, "the newest message stays exact")
        self.assertLess(len(out), len(messages))

    def test_the_layer_is_the_compaction_summary(self):
        engine = self.engine(window=4000)
        try:
            text = ace.layer(engine, chat(60))
        finally:
            engine.close_all()
        self.assertTrue(text)

    def test_each_request_writes_one_line_to_ace_log(self):
        engine = self.engine(window=4000)
        try:
            ace.select(engine, chat(60))
        finally:
            engine.close_all()
        log = os.path.join(ace.home(self.cwd), "ace.log")
        with open(log, encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("sess=ses_1", lines[0])

    def test_a_folder_is_its_own_memory_and_the_home_folder_is_the_default(self):
        project = os.path.join(os.path.dirname(self.base), "kettle")
        os.makedirs(os.path.join(project, ".git"))
        self.assertIn(os.sep + "scopes" + os.sep, ace.home(project))
        self.assertIn(os.sep + "scopes" + os.sep, ace.home(self.cwd))  # no git: the folder itself is the project
        self.assertEqual(os.path.realpath(ace.home(os.path.expanduser("~"))), os.path.realpath(self.base))

    def test_the_main_reads_json_and_answers_with_json(self):
        import io
        req = json.dumps({"op": "select", "sid": "ses_2", "cwd": self.cwd, "model": "demo-model",
                          "messages": [{"role": "user", "content": "hi"}]})
        out = io.StringIO()
        ace.main(stdin=io.StringIO(req), stdout=out)
        self.assertEqual(json.loads(out.getvalue()), {"messages": None})

    def test_a_bad_request_answers_an_error_and_does_not_raise(self):
        import io
        out = io.StringIO()
        code = ace.main(stdin=io.StringIO("{not json"), stdout=out)
        self.assertEqual(code, 0)
        self.assertIn("error", json.loads(out.getvalue()))


if __name__ == "__main__":
    unittest.main()
