import unittest

from utils.command_line import (
    CommandRequest,
    HelpRequested,
    ParseError,
    parse_command_switches,
    startup_action,
)


class ParseCommandSwitchesTests(unittest.TestCase):
    def test_no_arguments_is_an_empty_request(self):
        request = parse_command_switches([])
        self.assertFalse(request.has_commands())
        self.assertEqual(request.steps(), [])

    def test_mediarecorder_style_switches_are_recognised(self):
        request = parse_command_switches(["/E", "/R", "/S", "/X"])
        self.assertTrue(request.launch)
        self.assertTrue(request.record)
        self.assertTrue(request.stop)
        self.assertTrue(request.close)

    def test_switches_are_case_insensitive_and_accept_dash_prefix(self):
        request = parse_command_switches(["-r", "--S", "/x"])
        self.assertTrue(request.record)
        self.assertTrue(request.stop)
        self.assertTrue(request.close)

    def test_preset_and_base_name_take_values_after_equals_or_colon(self):
        request = parse_command_switches(["/C=Lab 1", "/B:Trial_07"])
        self.assertEqual(request.preset, "Lab 1")
        self.assertEqual(request.base_name, "Trial_07")

    def test_preset_value_may_be_a_json_path_with_spaces(self):
        request = parse_command_switches([r"/C=C:\Presets\Two cameras.json"])
        self.assertEqual(request.preset, r"C:\Presets\Two cameras.json")

    def test_value_switch_without_a_value_is_an_error(self):
        with self.assertRaises(ParseError):
            parse_command_switches(["/C"])
        with self.assertRaises(ParseError):
            parse_command_switches(["/B="])

    def test_unknown_switch_is_an_error(self):
        with self.assertRaises(ParseError) as raised:
            parse_command_switches(["/Q"])
        self.assertIn("/Q", str(raised.exception))

    def test_help_switches_raise_help_with_the_switch_summary(self):
        for argv in (["/?"], ["/h"], ["--help"]):
            with self.assertRaises(HelpRequested) as raised:
                parse_command_switches(argv)
            self.assertIn("/R", str(raised.exception))

    def test_steps_run_in_a_fixed_order_regardless_of_argument_order(self):
        request = parse_command_switches(["/X", "/R", "/B=Run", "/S", "/C=Lab"])
        self.assertEqual(
            request.steps(),
            [("preset", "Lab"), ("base_name", "Run"), ("record", None), ("stop", None), ("close", None)],
        )

    def test_request_round_trips_through_json(self):
        request = parse_command_switches(["/E", "/C=Lab", "/B=Run", "/R"])
        again = CommandRequest.from_json(request.to_json())
        self.assertEqual(again, request)


class StartupActionTests(unittest.TestCase):
    def test_plain_launch_with_no_switches_starts_the_window(self):
        self.assertEqual(startup_action(parse_command_switches([]), already_running=False), "launch")

    def test_plain_launch_when_running_shows_the_already_running_notice(self):
        self.assertEqual(startup_action(parse_command_switches([]), already_running=True), "already_running")

    def test_switches_are_sent_to_the_running_instance(self):
        self.assertEqual(startup_action(parse_command_switches(["/R"]), already_running=True), "send")
        self.assertEqual(startup_action(parse_command_switches(["/E"]), already_running=True), "send")

    def test_record_or_preset_switches_launch_nvc_when_it_is_not_running(self):
        for argv in (["/R"], ["/E"], ["/C=Lab"], ["/B=Run"], ["/E", "/C=Lab", "/R"]):
            self.assertEqual(startup_action(parse_command_switches(argv), already_running=False), "launch", argv)

    def test_stop_or_close_alone_has_nothing_to_do_when_nvc_is_not_running(self):
        for argv in (["/S"], ["/X"], ["/S", "/X"]):
            self.assertEqual(startup_action(parse_command_switches(argv), already_running=False), "nothing", argv)


if __name__ == "__main__":
    unittest.main()
