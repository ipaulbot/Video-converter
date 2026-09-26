# Portfolio / resume site — design and first build

Date: 2026-09-26. Companion to
`docs/planning/2026-09-26-product-naming-website-and-github.md` (section 3),
which this narrows from "product site with Buy" to the piece asked for now:
**a landing page for the owner's projects plus a resume**. Buy/licensing pages
stay in the planning doc until the licensing decisions are made.

Built at `D:\Python Projects\portfolio-site` as its own git repository (one
commit). It is not part of the NVC repo: the site outlives any one product and
must never carry product source or settings.

## Reference

Inspiration: https://matthewthompson.dev/#portfolio — one long page, sticky
nav (About · Skills · Projects · Contact), hero with a one-line positioning
statement, three expertise cards, numbered skill cards that expand into
"experience" bullets with tag chips, featured project cards with tag chips and
a status/meta line ("Live · …"), contact buttons. Taken from it: the
structure, the numbered expandable skill cards, the tag-chip vocabulary, the
meta line. Not taken: the "Insights" blog, site search, external fonts,
analytics.

## Shape

```
content.py   single source of truth (identity, about, skills, projects, resume)
build.py     std-lib only; renders docs/index.html + docs/resume.html, copies assets/
assets/      site.css (system fonts, light/dark via prefers-color-scheme, print rules),
             site.js (mobile menu, active-section nav, year), img/ (help figures)
docs/        generated; GitHub Pages serves this folder (`.nojekyll` written)
tests/       unittest: every project/skill rendered, images exist, no personal
             paths or credentialled URLs, resume links only to real projects
```

Sections on `index.html`: hero → About (prose + three expertise cards) →
Skills (numbered `<details>` cards) → Projects (cards: image, summary, tags,
highlights, thumbnail gallery, meta + links) → Contact. `resume.html`: summary,
experience, selected projects (linking back to the cards), education, skills;
prints cleanly; "Download PDF" appears once `CONTACT["resume_pdf"]` is set.

## Privacy rules baked in

- Identity, location, contact and resume entries are `TODO` placeholders; the
  build lists every remaining placeholder and `--check` fails on them. Nothing
  about the owner is derived from this machine.
- `build.py` refuses to write output containing a `C:\Users\…` path or an
  `rtsp://user:pass@` URL.
- Screenshots are copies of the help-manual figures (captured off-screen from
  stub data): NVC `fig-00/06/07/08`, VIO `FIG-00/03/12`. Both were looked at
  before copying; no desktop, user name or personal device appears.

## Content decisions made for the owner (edit freely)

- Positioning line: "I build the tools that sit between researchers and their
  hardware." Title: "Software engineer · Lab automation · Desktop tools".
- Four real skill groups (Python application engineering; Video, audio &
  devices; Hardware & protocol emulation; Documentation & localisation) with
  experience bullets drawn from the two products; a fifth is a placeholder.
- Projects: NVC, Virtual IO Box, "This website", one placeholder card.
- No product download links yet (commented out in `content.py`) — they need
  the GitHub decision from the planning doc.

## Open questions for the owner (asked in the 18:16 report)

Public name/title; whether the two products may be shown publicly given the
employer branding visible in both apps (logo, "NOLDUS" on the VIO faceplate,
settings under a `Noldus` folder) and how to describe that relationship;
which other projects to include (folder locations + one paragraph each);
resume facts (roles, dates, education, links); hosting/domain; photo or logo;
colour preference beyond the products' teal.

## Deploy

GitHub Pages, branch `main`, folder `/docs`. A user site
(`<username>.github.io`) serves at the root; any other repo name serves under
`/<repo>/` (all links are relative, so both work). Custom domain via the Pages
settings; the build does not need it.
