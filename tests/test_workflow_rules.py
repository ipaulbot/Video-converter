import unittest

from ui.workflow_rules import Activity, blocked_reason, status_markup, status_parts


class BlockedReasonTests(unittest.TestCase):
    def test_idle_allows_every_action(self):
        for action in ("convert", "record", "lossless_edit"):
            self.assertEqual(blocked_reason(Activity(), action), "")

    def test_locked_blocks_every_start_action(self):
        locked = Activity(locked=True)
        for action in ("convert", "record", "lossless_edit"):
            self.assertIn("locked", blocked_reason(locked, action).lower())

    def test_recording_blocks_conversion_and_lossless_edits_but_not_viewing(self):
        for phase in ("starting", "recording", "stopping"):
            recording = Activity(recording_phase=phase)
            self.assertIn("recording", blocked_reason(recording, "convert").lower())
            self.assertIn("recording", blocked_reason(recording, "lossless_edit").lower())
        # A failed recording is over: nothing is blocked by it.
        self.assertEqual(blocked_reason(Activity(recording_phase="failed"), "convert"), "")

    def test_conversion_or_monitoring_blocks_recording_only(self):
        for activity in (Activity(converting=1), Activity(monitoring=True)):
            self.assertIn("conversion", blocked_reason(activity, "record").lower())
            self.assertEqual(blocked_reason(activity, "convert"), "")
            self.assertEqual(blocked_reason(activity, "lossless_edit"), "")

    def test_unknown_actions_are_never_blocked(self):
        self.assertEqual(blocked_reason(Activity(recording_phase="recording"), "inspect"), "")


class StatusTests(unittest.TestCase):
    def test_idle_reads_idle_in_teal(self):
        self.assertEqual(status_parts(Activity()), ["Idle"])
        markup = status_markup(Activity())
        self.assertTrue(markup.startswith("Status: Idle"))
        self.assertIn("#43a296", markup)

    def test_every_active_job_is_listed_in_a_fixed_order(self):
        activity = Activity(recording_phase="recording", converting=2, monitoring=True)
        self.assertEqual(status_parts(activity), ["Recording", "Converting", "Monitoring"])
        self.assertIn("Recording · Converting · Monitoring", status_markup(activity))
        self.assertIn("#00cc00", status_markup(activity))

    def test_recording_phases_have_their_own_words(self):
        self.assertEqual(status_parts(Activity(recording_phase="starting")), ["Starting recording"])
        self.assertEqual(status_parts(Activity(recording_phase="stopping")), ["Stopping recording"])
        self.assertEqual(status_parts(Activity(recording_phase="failed")), ["Recording failed"])
        self.assertIn("#dc3545", status_markup(Activity(recording_phase="failed")))

    def test_locked_comes_first_and_greys_the_dot(self):
        activity = Activity(locked=True, converting=1)
        self.assertEqual(status_parts(activity), ["Locked", "Converting"])
        self.assertIn("#888888", status_markup(activity))

    def test_monitoring_alone_keeps_the_amber_dot(self):
        self.assertIn("#FFD700", status_markup(Activity(monitoring=True)))


if __name__ == "__main__":
    unittest.main()
