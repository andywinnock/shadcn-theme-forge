from __future__ import annotations

import unittest

import gallery


class GalleryReleaseUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.themes = gallery.load_themes()
        cls.generated = gallery.build_html(cls.themes)

    def test_narrow_layout_rules_bound_dense_gallery_surfaces(self) -> None:
        for rule in (
            "@media(max-width:560px)",
            ".theme-control{order:3;width:100%;min-width:0}",
            "@media(max-width:720px)",
            ".dashboard-grid,.dash-second,.token-strip{grid-template-columns:minmax(0,1fr)}",
            ".dash-button-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:100%}",
            ".dash-second>.dash-card{overflow-x:auto}",
            ".dash-table{min-width:32rem}",
            "@media(max-width:380px){.dash-button-row{grid-template-columns:minmax(0,1fr)}}",
            ".shell-grid,.shell-lower{grid-template-columns:minmax(0,1fr)}",
            ".shell-card,.shell-card *{min-width:0}",
            "overflow-wrap:anywhere",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, self.generated)

    def test_primary_mobile_controls_keep_touch_sized_targets(self) -> None:
        self.assertIn(".theme-control select{min-height:44px}", self.generated)
        self.assertIn(".mode-toggle{min-height:44px}", self.generated)
        self.assertIn("@media(max-width:600px)", self.generated)
        self.assertIn(".button{min-height:44px}", self.generated)

    def test_release_and_diagnostic_copy_is_derived_or_explicitly_inert(self) -> None:
        self.assertIn(f"{len(self.themes)} presets · Offline", self.generated)
        self.assertIn(f"Theme presets <span>{len(self.themes)}</span>", self.generated)
        for honest_label in (
            "Adapter list specimen",
            "Progress specimen",
            "Inert adapter table specimen",
            "Local specimen gallery",
            "Example helper text; no generated metadata is asserted.",
            "Readonly path specimen",
            "Destructive-action specimen; no files are changed.",
            'data-preview="inert"',
        ):
            with self.subTest(label=honest_label):
                self.assertIn(honest_label, self.generated)
        for stale_claim in (
            "512 variables",
            "Tailwind Config",
            "187 components",
            "TypeScript Types",
            "Today, 10:24 AM",
            "Theme Forge v1.0.0",
            "Six adapters are ready for review",
            "Theme assets are ready",
            "3 packages can be updated",
            "All local assets passed validation",
            "All template placeholders resolved",
            "Shown in generated asset metadata.",
            "Generated path",
            "out/themes/current",
            "Deleting generated assets does not change the registry.",
            "Delete generated assets",
        ):
            with self.subTest(claim=stale_claim):
                self.assertNotIn(stale_claim, self.generated)


if __name__ == "__main__":
    unittest.main()
