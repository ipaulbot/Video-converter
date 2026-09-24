import unittest

from pc_report import registry
from pc_report.section import GROUPS, Section


class RegistryInvariantTests(unittest.TestCase):
    def test_every_section_is_in_order_and_unique(self):
        keys = [s.key for s in registry.SECTIONS]
        self.assertEqual(len(keys), len(set(keys)))
        for key in keys:
            self.assertIn(key, registry.ORDER)
        self.assertEqual(keys, sorted(keys, key=registry.ORDER.index))

    def test_groups_are_known_and_callables_present(self):
        for section in registry.SECTIONS:
            self.assertIn(section.group, GROUPS, section.key)
            self.assertTrue(callable(section.collect), section.key)
            self.assertTrue(callable(section.render), section.key)
            self.assertGreaterEqual(section.timeout, 12, section.key)

    def test_after_names_existing_keys_without_cycles(self):
        keys = {s.key for s in registry.SECTIONS}
        for section in registry.SECTIONS:
            for dep in section.after:
                self.assertIn(dep, keys, f"{section.key} depends on unknown {dep}")
        # Kahn's algorithm: every section must be reachable.
        remaining = {s.key: set(s.after) for s in registry.SECTIONS}
        while remaining:
            ready = [k for k, deps in remaining.items() if not deps]
            self.assertTrue(ready, f"dependency cycle among {sorted(remaining)}")
            for k in ready:
                del remaining[k]
            for deps in remaining.values():
                deps.difference_update(ready)

    def test_render_survives_empty_and_partial(self):
        from pc_report.section import RenderContext
        ctx = RenderContext(redact=True, meta={})
        for section in registry.SECTIONS:
            for payload in ({}, None, []):
                out = section.render(payload, ctx)
                self.assertIsInstance(out, str, section.key)

    def test_order_covers_the_spec_and_alias_targets_exist_in_order(self):
        self.assertEqual(len(registry.ORDER), 40)
        self.assertEqual(registry.ORDER[0], "noldus_summary")
        for alias, targets in registry.ALIASES.items():
            for target in targets:
                self.assertIn(target, registry.ORDER, alias)


class SelectionTests(unittest.TestCase):
    def _sections(self):
        mk = lambda key, on=True: Section(key=key, title=key, group="Hardware",  # noqa: E731
                                          collect=lambda c: {}, render=lambda d, c: "", default_on=on)
        return [mk("cpu"), mk("memory"), mk("shares"), mk("processes", on=False)]

    def test_default_on_respected(self):
        keys = [s.key for s in registry.select({}, self._sections())]
        self.assertEqual(keys, ["cpu", "memory", "shares"])

    def test_explicit_switches(self):
        keys = [s.key for s in registry.select({"cpu": False, "processes": True}, self._sections())]
        self.assertEqual(keys, ["memory", "shares", "processes"])

    def test_group_alias_switches_split_sections(self):
        keys = [s.key for s in registry.select({"hardware": False}, self._sections())]
        self.assertEqual(keys, ["shares"])
        keys = [s.key for s in registry.select({"network": False}, self._sections())]
        self.assertEqual(keys, ["cpu", "memory"])

    def test_explicit_key_beats_alias(self):
        keys = [s.key for s in registry.select({"hardware": False, "cpu": True}, self._sections())]
        self.assertEqual(keys, ["cpu", "shares"])

    def test_grouped_keeps_group_order(self):
        grouped = registry.grouped(self._sections())
        self.assertEqual(list(grouped), list(GROUPS))
        self.assertEqual([s.key for s in grouped["Hardware"]], ["cpu", "memory", "shares", "processes"])
