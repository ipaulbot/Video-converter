import unittest

from pc_report.sections import virtual_machine as mod
from tests.pc_report import support


class BuildTests(unittest.TestCase):
    def test_physical_host_with_hyper_v(self):
        rows = mod.flatten(mod.build({"Manufacturer": "Dell Inc.", "Model": "Precision 3660", "HypervisorPresent": True},
                                     {"Manufacturer": "Dell Inc.", "Version": "DELL - 1", "BaseBoardManufacturer": "Dell Inc.", "BaseBoardProduct": "0ABC"},
                                     [{"Name": "vmms", "State": "Running", "StartMode": "Auto"}, {"Name": "vmcompute", "State": "Stopped", "StartMode": "Manual"}],
                                     [{"Name": "Intel Ethernet", "PNPClass": "Net"}]))
        self.assertEqual(rows["Running Inside a VM"], "No")
        self.assertEqual(rows["Hypervisor Present"], "Yes")
        self.assertEqual(rows["Interpretation"], "Physical machine with a hypervisor active (Hyper-V role, VBS or WSL 2)")
        self.assertEqual(rows["Hyper-V Management (vmms)"], "Running (Auto)")

    def test_vmware_guest(self):
        rows = mod.flatten(mod.build({"Manufacturer": "VMware, Inc.", "Model": "VMware20,1", "HypervisorPresent": True}, {}, [],
                                     [{"Name": "VMware SVGA 3D", "PNPClass": "Display"}, {"Name": "VMware VMCI Bus Device", "PNPClass": "System"}]))
        self.assertEqual(rows["Running Inside a VM"], "Yes")
        self.assertEqual(rows["Detected Hypervisor"], "VMware")
        self.assertIn("VMware SVGA 3D", rows["Guest Device Markers"])

    def test_detect(self):
        self.assertEqual(mod.detect_vendor("innotek GmbH", "VirtualBox", ""), "VirtualBox")
        self.assertEqual(mod.detect_vendor("Microsoft Corporation", "Virtual Machine", ""), "Hyper-V")
        self.assertEqual(mod.detect_vendor("QEMU", "Standard PC (Q35)", ""), "QEMU/KVM")
        self.assertEqual(mod.detect_vendor("Dell Inc.", "OptiPlex", ""), "")

    def test_cloud_and_guest_service_markers(self):
        self.assertEqual(mod.detect_vendor("Amazon EC2", "t3.large", ""), "Amazon EC2")
        self.assertEqual(mod.detect_vendor("Google", "Google Compute Engine", ""), "Google Compute Engine")
        rows = mod.flatten(mod.build(
            {"Manufacturer": "Generic", "Model": "Generic", "HypervisorPresent": False},
            {},
            {"Name": "QEMU Guest Agent", "State": "Running", "StartMode": "Auto"},
            [],
        ))
        self.assertEqual(rows["Running Inside a VM"], "Yes")
        self.assertEqual(rows["Detected Hypervisor"], "QEMU/KVM")

    def test_single_strong_device_marker_detects_guest(self):
        rows = mod.flatten(mod.build(
            {"Manufacturer": "Generic", "Model": "Generic", "HypervisorPresent": "False"},
            {},
            [],
            {"Name": "Red Hat VirtIO Ethernet Adapter", "PNPClass": "Net"},
        ))
        self.assertEqual(rows["Running Inside a VM"], "Yes")
        self.assertEqual(rows["Detected Hypervisor"], "QEMU/KVM")
        self.assertEqual(rows["Hypervisor Present"], "No")


class FixtureTests(unittest.TestCase):
    def test_collect_and_render_from_fixtures(self):
        _data, html, ctx = support.collect_and_render(mod.SECTION)
        self.assertEqual([n for n in ctx.notes if "no fixture" in n], [])
        self.assertIn("<th>Running Inside a VM</th>", html)

    def test_renders_empty(self):
        support.assert_renders_empty(self, mod.SECTION)
