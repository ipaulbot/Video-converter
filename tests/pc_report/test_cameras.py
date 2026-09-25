import unittest

from pc_report.privacy import redact_payload
from pc_report.sections import cameras as mod
from tests.pc_report import support

PNP = [{"Name": "Basler ace acA1920-40uc", "Manufacturer": "Basler", "PNPClass": "Camera", "Status": "OK", "ConfigManagerErrorCode": 0,
        "Service": "usbvideo", "Present": True, "PNPDeviceID": "USB\\VID_2676&PID_BA02\\123", "DeviceID": "USB\\VID_2676&PID_BA02\\123"},
       {"Name": "Intel Ethernet", "PNPClass": "Net", "Status": "OK", "ConfigManagerErrorCode": 0, "Present": True, "PNPDeviceID": "PCI\\1"},
       {"Name": "Integrated Webcam", "Manufacturer": "Microsoft", "PNPClass": "Image", "Status": "Error", "ConfigManagerErrorCode": 22,
        "Service": "usbvideo", "Present": True, "PNPDeviceID": "USB\\VID_0C45&PID_6A10\\1", "DeviceID": "USB\\VID_0C45&PID_6A10\\1"},
       {"Name": "Canon TR8500 series", "Manufacturer": "Canon", "PNPClass": "Image", "Status": "OK", "ConfigManagerErrorCode": 0,
        "Service": "StillCam", "Present": True, "PNPDeviceID": "USB\\VID_04A9&PID_1825\\2"}]
DS = [{"Category": "Video Capture Sources", "Name": "Basler ace acA1920-40uc", "CLSID": "{860BB310-5D01-11d0-BD3B-00A0C911CE86}",
       "DevicePath": "\\\\?\\usb#vid_2676&pid_ba02#123#{65e8773d}", "Architecture": "x64"},
      {"Category": "Audio Capture Sources", "Name": "Microphone (USB Camera)", "CLSID": "{33D9A762}", "DevicePath": "", "Architecture": "x64"}]
DX = {"VideoCaptureDevices": {"VideoCaptureDevice": {"FriendlyName": "Basler ace acA1920-40uc", "Category": "Camera", "Manufacturer": "Basler",
                                                     "HardwareID": "USB\\VID_2676&PID_BA02&REV_0100", "DriverDesc": "USB Video Device",
                                                     "DriverProvider": "Microsoft", "DriverVersion": "10.0.26100.1", "DriverDateEnglish": "6/21/2006",
                                                     "Service": "usbvideo", "Class": "Camera", "ProblemCode": "No Problem", "Location": "Port_#0001.Hub_#0002"}}}
FS = {"EnableFrameServerMode": 0, "EnableFrameServerModeWow": None, "FrameServerStatus": "Stopped", "FrameServerStartType": "Manual"}
CONSENT = [{"Capability": "webcam", "Hive": "HKCU", "App": "(global)", "Value": "Allow", "LastUsedStart": None, "LastUsedStop": None},
           {"Capability": "webcam", "Hive": "HKCU", "App": "C:#Program Files#Noldus#EthoVision.exe", "Value": "Allow",
            "LastUsedStart": 133700000000000000, "LastUsedStop": 133700000000000000},
           {"Capability": "microphone", "Hive": "HKCU", "App": "C:#Program Files#Noldus#EthoVision.exe", "Value": "Prompt",
            "LastUsedStart": 133600000000000000, "LastUsedStop": 133800000000000000},
           {"Capability": "microphone", "Hive": "HKLM", "App": "(global)", "Value": "Deny", "LastUsedStart": None, "LastUsedStop": None}]
ENV = [{"Name": "GENICAM_GENTL64_PATH", "Value": "C:\\Program Files\\Basler\\pylon 7\\Runtime\\x64\\;C:\\Program Files\\Common Files\\Noldus\\GenTL\\"}]
PROGRAMS = [{"Name": "pylon 7.4 Camera Software Suite", "Version": "7.4.0", "Publisher": "Basler AG"},
            {"Name": "Basler GigE Vision Transport Layer", "Version": "7.4.0", "Publisher": "Basler AG"},
            {"Name": "7-Zip", "Version": "23.01", "Publisher": "Igor Pavlov"}]


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.data = mod.build(PNP, DS, DX, FS, CONSENT, ENV, PROGRAMS)
        self.rows = mod.flatten(self.data)

    def test_pnp_cameras_only(self):
        names = [r["Name"] for r in self.data["pnp"]]
        self.assertEqual(names, ["Basler ace acA1920-40uc", "Integrated Webcam"])
        self.assertEqual(self.data["pnp"][1]["Problem"], "22: Disabled")
        self.assertEqual(mod.camera_names(self.data), names)

    def test_camera_classification(self):
        cases = [
            ({"PNPClass": "Image", "Name": "Canon TR8500 series", "Service": "StillCam"}, False),
            ({"PNPClass": "Image", "Name": "Generic imaging device", "Service": "USBVideo"}, True),
            ({"PNPClass": "Camera", "Name": "Industrial sensor", "Service": ""}, True),
            ({"PNPClass": "Media", "Name": "USB Camera Pro", "Service": ""}, True),
            (
                {
                    "PNPClass": "MEDIA",
                    "Name": "HD Pro Webcam C920",
                    "Service": "usbaudio",
                    "Description": "USB Audio Device",
                },
                False,
            ),
            ({"PNPClass": "Camera", "Name": "HD Pro Webcam C920", "Service": "usbvideo"}, True),
            ({"PNPClass": "MEDIA", "Name": "HD Pro Webcam C920", "Service": "usbvideo"}, True),
        ]
        for row, expected in cases:
            with self.subTest(row=row):
                self.assertIs(mod.is_camera(row), expected)

    def test_camera_names_deduplicates_preserving_order(self):
        data = {
            "pnp": [
                {"Name": "HD Pro Webcam C920", "Class": "Camera", "Service": "usbvideo"},
                {"Name": "Integrated Webcam", "Class": "Camera", "Service": "usbvideo"},
                {"Name": "HD Pro Webcam C920", "Class": "Camera", "Service": "usbvideo"},
            ]
        }
        self.assertEqual(
            mod.camera_names(data),
            ["HD Pro Webcam C920", "Integrated Webcam"],
        )

    def test_frame_server_and_consent(self):
        self.assertEqual(self.rows["Frame Server Mode"], "Disabled (exclusive camera access for legacy applications)")
        self.assertEqual(self.rows["Frame Server Service"], "Stopped (Manual)")
        self.assertEqual(self.rows["Camera Access (user)"], "Allow")
        self.assertEqual(self.rows["Microphone Access (machine policy)"], "Deny")
        self.assertEqual(mod.denied(self.data), ["Microphone (machine policy)"])
        app = self.data["consent_apps"][0]
        self.assertEqual(app["App"], "C:\\Program Files\\Noldus\\EthoVision.exe")
        self.assertEqual(app["Camera"], "Allow")
        self.assertEqual(app["Microphone"], "Prompt")
        self.assertRegex(app["Last Used"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(len(self.data["consent_apps"]), 1)

    def test_genicam_and_transport_layers(self):
        self.assertEqual(self.rows["GENICAM_GENTL64_PATH"], ["C:\\Program Files\\Basler\\pylon 7\\Runtime\\x64\\", "C:\\Program Files\\Common Files\\Noldus\\GenTL\\"])
        self.assertEqual(self.rows["Detected Camera Transport Layers"],
                         ["Basler: Basler GigE Vision Transport Layer 7.4.0", "Basler: pylon 7.4 Camera Software Suite 7.4.0"])

    def test_transport_patterns_cover_supported_vendors(self):
        cases = {
            "pylon 7 Camera Software Suite": "Basler",
            "MATRIX VISION mvIMPACT Acquire": "MATRIX VISION",
            "FLIR Spinnaker SDK": "FLIR",
            "IDS peak": "IDS",
            "Allied Vision Vimba X": "Allied Vision",
            "Teledyne DALSA Sapera LT": "Teledyne DALSA",
            "Lucid Arena SDK": "Lucid",
            "The Imaging Source IC Imaging Control": "The Imaging Source",
        }
        for name, vendor in cases.items():
            with self.subTest(name=name):
                matches = [label for pattern, label in mod.TRANSPORT_PATTERNS if pattern.search(name)]
                self.assertIn(vendor, matches)
        self.assertFalse(any(pattern.search("Microsoft Edge") for pattern, _label in mod.TRANSPORT_PATTERNS))

    def test_sources_and_dxdiag(self):
        self.assertEqual(self.data["video_sources"][0]["Device Path"], "\\\\?\\usb#vid_2676&pid_ba02#123#{65e8773d}")
        self.assertEqual(self.data["audio_sources"][0]["Name"], "Microphone (USB Camera)")
        self.assertEqual(self.data["dxdiag"][0]["Driver"], "USB Video Device 10.0.26100.1 (Microsoft)")

    def test_filetime(self):
        self.assertEqual(mod.filetime(0), "")
        self.assertRegex(mod.filetime(133700000000000000), r"^\d{4}-")


class PrivacyTests(unittest.TestCase):
    def test_a_directshow_device_path_loses_its_instance_segment(self):
        device_path = r"\\?\usb#vid_2676&pid_ba02#CAMSERIAL9#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
        ds = [{**DS[0], "DevicePath": device_path}]

        data = mod.build(PNP, ds, DX, FS, CONSENT, ENV, PROGRAMS)
        html = mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

        self.assertNotIn("CAMSERIAL9", html)
        self.assertNotIn("65e8773d-8f56-11d0", html)
        # The vendor and product IDs identify the camera model, not the unit.
        self.assertIn("vid_2676", html)

    def test_a_personal_camera_name_is_masked_in_every_table(self):
        pnp = [{**PNP[0], "Name": "Jan's iPhone"}]
        ds = [{**DS[0], "Name": "Jan's iPhone"}]

        data = mod.build(pnp, ds, DX, FS, CONSENT, ENV, PROGRAMS)
        html = mod.render(redact_payload(data, {"redact": True}, env={}), support.render_ctx())

        self.assertNotIn("Jan", html)


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        programs = {"installed_programs": {"data": {"rows": PROGRAMS}, "notes": []}}
        _data, html, ctx = support.collect_and_render(mod.SECTION, results=programs)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Frame Server Mode</th>", html)
        self.assertIn("<h3>DirectShow video capture sources</h3>", html)
        self.assertLess(html.count("<tr>"), 90)
        self.assertNotIn("Canon TR8500 series", mod.camera_names(_data))
        self.assertEqual(
            mod.camera_names(_data),
            ["HD Pro Webcam C920", "Integrated Webcam"],
        )

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
