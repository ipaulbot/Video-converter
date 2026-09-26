# Product naming, a landing-page site, and a GitHub presence

Status: planning only. Nothing in this document has been built; no rename,
website or repository change has been made. It records the 2026-09-26 request
("eventually") and an opinion, so the work can start from a decision rather
than from scratch. Companion: `2026-09-26-licensing-and-commercial-release-plan.md`
covers what has to be true before anything is sold.

## 1. The ask

1. A landing-page website for the owner's products (this app and Virtual IO
   Box, with room for more) that serves three purposes at once: a place to
   **buy**, a place to **preview** (screenshots, short videos, the help
   documents) and a place to show the owner's **resume**.
2. **One voice across the products.** Virtual IO Box and this app should read
   as if the same person wrote them: names, tab and button language, help
   documents, installer text.
3. A **GitHub presence** that shows the work is real and maintained.
4. Possibly **rename this app** ("Media Multitool" was floated; the owner is
   not sure).

## 2. Naming

### Where the name stands today

The app is called three things at once:

| Where                    | Name                                     |
|--------------------------|------------------------------------------|
| Window title, installer  | `Video Converter v2.3.0`                 |
| Short name, exe, help    | `NVC`                                    |
| Its own tabs             | Video Converter, Multi-Source Recorder, Lossless Editor, Media Player (with Inspect), PC Report |

"Video Converter" describes one of five tabs. Someone who only reads the
title never learns that it records four cameras, trims losslessly, plays four
clips in sync or inspects a file. That is the real argument for a rename; the
tab merge and header work this month made the app visibly a suite.

### Opinion

- **Rename, but not to "Media Multitool".** It is honest and descriptive,
  which is why it comes to mind, and that is also its weakness: it is a
  category, not a name. It is hard to search for, impossible to own, and it
  sounds like a free utility rather than a product someone pays for. It also
  sits awkwardly next to "Virtual IO Box", which is a compact proper name.
- **Pick a short proper name plus a descriptor**, the pattern Virtual IO Box
  already follows. The descriptor does the explaining ("record, convert,
  edit and review video"); the name does the remembering. Candidates worth
  a short shortlist exercise (check trademarks, domains and app-store
  collisions before falling in love with any): a made-up two-syllable word,
  or a plain noun with a video sense (a "reel", "frame", "take", "cut").
- **Keep `NVC` as the internal / file-system identifier** regardless of the
  public name: exe name, settings folder, installer id, log names. Renaming
  those breaks upgrades (settings live under a fixed public-documents path)
  and buys nothing a user sees. Public name in the title bar, installer page
  and website; `NVC` under the hood, exactly as `VIO` is for Virtual IO Box.
- **Decide once, then apply everywhere in one lead**: `ui/main_window.py`
  title, `installer/*.iss` display name, help-document titles
  (`docs/help/source/document_registry.py`), the README, the website. The
  i18n catalogues (`nl`, `zh_CN`) need the new title string translated.

### One voice across both products

Cheap, high-value, and independent of the rename:

- Same header pattern on every tab (done here 2026-09-26: glyph + title +
  one-line description). Virtual IO Box should adopt the same three-part
  header.
- Same words for the same things: "Settings" not "Preferences"/"Options",
  "Device" not "Source"/"Unit" where they mean the same, "Compact / Full
  window" for the two layout modes, identical burger-menu ordering (Settings,
  Help, About, Exit).
- Same document set per product, same naming: `<Product> <version> - Help`,
  `Quick Start Guide`, `Technical Spec`, `Developer Guide`, in `en`, `nl`,
  `zh-CN`. Virtual IO Box already has this; NVC's help set should match it.
- Same About dialog layout: product name, version, one-line description,
  licence line, link to the website and to the repository.
- A tiny shared style sheet (colours, corner radius, glyph stroke) is worth
  more than shared code between two separate apps. Both are PyQt5 and both
  already paint glyphs at runtime; lifting `glyph_icons.py` and the theme
  tokens into a small shared package is the first refactor to consider,
  after the rename is settled.

## 3. The landing-page website

### Shape

One static site, no server-side code, one page per product plus three
shared pages:

```
/                 home: what the studio makes, two product cards, contact
/nvc/             NVC (or new name): pitch, screenshots, feature grid, download / buy
/virtual-io-box/  VIO: same template
/docs/            the generated PDFs / HTML help for both products, per language
/resume/          resume (HTML + PDF download)
/buy/             checkout or "request a licence" form (see below)
```

Static hosting (GitHub Pages, Cloudflare Pages or Netlify) costs nothing,
handles the traffic a product site gets, and the HTML can be generated
from the same Python content files that already produce the help PDFs, so
screenshots and feature text stay in sync with the apps.

### Preview

- Screenshots come from the existing off-screen capture scripts
  (`docs/help/source/capture_screenshots.py` here; the VIO equivalent), so
  they never show a real desktop, user name or device name. Re-run them
  per release; do not hand-crop.
- One 30–60 second silent screen recording per product, recorded with the
  Multi-Source Recorder's screen source itself (a good story for the page).
- Link the generated help PDFs rather than rewriting features in prose.

### Buy

This depends on decisions in the licensing plan (PyQt5 commercial licence
or PySide6 port, FFmpeg build, codec position). Until those are made,
"Buy" should be "Request a licence" (a form that emails the owner) or a
Gumroad / Lemon Squeezy / Paddle product link; those three handle VAT and
card processing and need no backend. Keep the licence-key check in the app
simple (signed key file) and out of scope for the site.

### Resume

A single HTML page with a PDF twin. Mention both products as shipped work
with links to their pages and repositories. No personal machine names,
addresses or phone numbers in the repository; the site's contact form and
the PDF can carry what the owner chooses to publish.

## 4. GitHub

None of this can be done from inside the app repository; it needs the
owner signed in to their account.

1. **Pick what is public.** Options: (a) the full source of both apps, (b) a
   public "showcase" repository per product with README, screenshots,
   releases (installers) and the help PDFs while source stays private, or
   (c) source public but vendor binaries (FFmpeg, IOWarrior DLLs) fetched at
   build time. (b) is the fastest route to "legitimacy" without a licensing
   decision; (c) is the usual end state.
2. **Repository hygiene before anything is pushed publicly**, per repo:
   - A README with one screenshot, a one-paragraph pitch, a feature list,
     "Download" (Releases) and "Build from source" sections, and licence.
   - `LICENSE` chosen (proprietary/EULA for the installers; the source
     licence depends on the PyQt decision).
   - Secrets and personal data audit: the leak-scan patterns used in this
     project's verification steps (machine names, user names, device names,
     camera URLs) run against the whole history, not just the tip; anything
     found means a history rewrite before the first public push.
   - `CHANGELOG.md` kept (this repo has one), tagged releases with the
     installer attached, a `SECURITY.md` and a short `CONTRIBUTING.md` even if
     contributions are not expected; they signal maintenance.
   - CI: a GitHub Actions workflow that runs `pytest` headless and `ruff` on
     push. The test suites already run headless, so this is mostly a YAML
     file and a Windows runner.
3. **Profile**: pin the two product repositories, set the profile README to
   the same pitch as the website home page, link the website.
4. **Releases as the download channel**: the website's download button
   points at the latest GitHub Release asset, so there is one place to
   publish an installer.

## 5. Order of work (when the time comes)

1. Naming decision (an afternoon; shortlist, checks, pick).
2. Licensing decisions from the companion plan (they gate "Buy" and the
   choice between public source and showcase repositories).
3. GitHub showcase repositories + Releases (a day): the fastest visible win.
4. Static site skeleton from the help content files (2–3 days), "Request a
   licence" form, resume page.
5. Apply the rename across both products and their help sets (one lead per
   product).
6. Shared style/glyph package across the two apps (later, optional).
