# NVC: what has to change before it can be sold

Status: planning only. Nothing in this document has been implemented; the
current build stays as it is until a decision is made on the open questions in
the last section.

This is an engineering inventory, not legal advice. Every item marked
**lawyer** should be confirmed by counsel before money changes hands; the rest
is work the codebase needs regardless of who reviews it.

## 1. Summary

NVC today is a GPL-licensed program whether or not anyone intended it: it
imports PyQt5 (GPL v3) and ships a GPL build of FFmpeg. Selling GPL software
is allowed, but every buyer must receive the source code and the right to
redistribute it. If NVC is to be sold as ordinary closed-source software, the
two GPL dependencies are the only hard blockers; everything else is
housekeeping (licence notices, third-party assets, trademarks, patents).

Blockers, in order of cost:

| # | Item | Why it blocks | Fix | Effort |
|---|------|---------------|-----|--------|
| 1 | PyQt5 (Riverbank) | GPL v3. Linking it makes NVC GPL. | Buy a Riverbank commercial licence **or** port to PySide6 (LGPL). | Licence: money, a day. Port: 1–2 weeks. |
| 2 | FFmpeg "full GPL" build (gyan.dev) | Contains libx264, libx265 and other GPL parts. | Run it as a separate process (already the case) and comply with GPL for the binary, **or** ship an LGPL build. | Compliance: 1–2 days. LGPL build: loses libx264/libx265, 2–4 days of rework. |
| 3 | `Paradise.mp3`, `Never-Gonna-Give-You-Up-3.mid` | Copyrighted music with no licence. | Remove from installer and repo. | Hours. |
| 4 | `team.png` and personal imagery | Likeness rights; not yours to sell. | Remove or replace with consent. | Hours. |
| 5 | Noldus names and paths | Trademark and "who owns this" questions. | Decide: product of Noldus, or independent. Rename accordingly. | Days, plus **lawyer**. |
| 6 | H.264 / HEVC encoders | Patent pools (Via LA / Access Advance). | Decide encoder strategy; possibly royalty or hardware-encoder-only. | **lawyer** |

## 2. Inventory of what NVC ships

### 2.1 Python dependencies (`requirements.txt`)

| Package | Licence | Consequence |
|---------|---------|-------------|
| PyQt5 >= 5.15 | GPL v3 **or** Riverbank commercial | The blocker. See §3. |
| Qt 5 itself (via PyQt5 wheels) | LGPL v3 / GPL v3 / commercial | LGPL is fine for closed source as long as the user can replace the Qt DLLs (PyInstaller onedir builds satisfy this; onefile does not, in the usual reading). |
| watchdog | Apache 2.0 | Ship the licence text and NOTICE. |
| requests (+ urllib3, certifi, idna, charset-normalizer) | Apache 2.0 / MIT / MPL 2.0 (certifi) | Ship licence texts. MPL requires that modified certifi sources be offered; it is unmodified. |
| Python 3.12 standard library | PSF licence | Ship the licence text. |

Dev-only (not shipped, no obligation): pytest (MIT), ruff (MIT), PyInstaller
(GPL with a bootloader exception that lets it build proprietary programs).

### 2.2 Binaries bundled by `NVC.spec`

| File | Source | Licence | Notes |
|------|--------|---------|-------|
| `ffmpeg.exe`, `ffprobe.exe` | gyan.dev "full" build, 2024-11-06 | **GPL v3** (because of libx264, libx265, libxvid, libvid.stab, etc.) | See §4. |
| Qt DLLs, PyQt5 `.pyd` | PyQt5 wheel | GPL/commercial (PyQt) + LGPL (Qt) | See §3. |
| Python runtime | python.org | PSF | Licence text. |

### 2.3 Assets in the repository or installer

| File | Problem |
|------|---------|
| `Paradise.mp3` (bundled by `NVC.spec`, played by the easter egg in `ui/dialogs.py` / `ui/extras/snood_widget.py`) | A commercial recording. There is no licence to redistribute it. Must go, or be replaced with a licensed / CC0 track. |
| `Never-Gonna-Give-You-Up-3.mid` (repo root) | Same; a MIDI arrangement is still a derivative of the composition. Remove from the repo. |
| `team.png` (shown in About) | Photos of identifiable people. Need their written consent for commercial use, or remove. |
| `graphics/*` icons, `BALLBUSTER.png`, `ITSAVIBE.png`, `level*.png`, `balls/` | Confirm every image was drawn in-house or comes with a commercial-use licence. Record the origin of each file in `graphics/SOURCES.md`. |
| Help PDFs (`docs/help`) | In-house; fine. Check screenshots contain no third-party UI or personal data. |
| Translations `.qm` | In-house; fine. |

### 2.4 Names, paths and third-party trademarks

- `utils/localization.py` registers settings under organisation **"Noldus"**.
- The recorder reads and writes `…\Documents\Noldus\NVC\MediaRecorder\Current Settings.json` to interoperate with Noldus MediaRecorder presets.
- `pc_report/noldus_summary.py`, `noldus_terms.py` and the `noldus_nvc_report` profile collect Noldus-specific driver and licence information.
- The help and CHANGELOG mention MediaRecorder and The Observer XT by name.

Interoperating with another vendor's file formats is normally fine; using
their name as part of your product, or implying endorsement, is not. The
bigger question is ownership (§7, question 1).

## 3. PyQt5: the decision

PyQt5 is dual-licensed. Under GPL v3, any program that imports it must itself
be distributed under GPL v3, with source. There is no LGPL option for PyQt.

### Option A: buy a Riverbank commercial licence

- Per-developer licence, one-off fee (check riverbankcomputing.com for current
  pricing; historically in the low hundreds of pounds per developer).
- Zero code changes.
- Every developer who works on the PyQt-using code needs one.
- Must be bought **before** the commercial version is built; Riverbank does not
  retroactively license GPL-era work.

### Option B: port to PySide6 (Qt for Python, LGPL v3)

- LGPL allows closed-source use if users can swap the Qt libraries; a
  PyInstaller **onedir** build does this naturally.
- Moves to Qt 6 at the same time: better HiDPI, but `QMediaPlayer`, `QAudio*`
  and the multimedia stack changed substantially and the Media Player tab
  would need rework.
- Known mechanical differences: `pyqtSignal` → `Signal`, `pyqtSlot` → `Slot`,
  `exec_()` → `exec()`, enums become scoped (`Qt.AlignmentFlag.AlignCenter`),
  `QAction` moves to `QtGui`, `sip` → `shiboken6`, `QDesktopWidget` is gone,
  `QRegExp` → `QRegularExpression`. The code base uses `sip.isdeleted`,
  `QDesktopServices`, `QPropertyAnimation`, `QGraphicsOpacityEffect`, all of
  which have direct equivalents.
- Estimate: 1–2 weeks including the test suite (~1400 tests), most of it
  mechanical, plus the Media Player rework.

### Recommendation

If more than one developer will ever touch the UI, or if Qt 6 is wanted
anyway, port to PySide6. If this is a one-developer product and shipping
soon matters, buy the licence. Either way this is the first decision to make
because it gates the build.

## 4. FFmpeg: GPL build vs LGPL build

NVC never links FFmpeg; it launches `ffmpeg.exe` as a child process and talks
to it over pipes and the command line. The FSF's view is that a separately
executed program is a separate work, so NVC itself does **not** become GPL
because of FFmpeg. What remains is that NVC *distributes* a GPL binary, and
that carries the GPL's obligations for that binary:

1. Include the GPL v3 licence text.
2. Give every recipient the complete corresponding source for exactly that
   build (or a written offer valid for three years). gyan.dev publishes
   source tarballs alongside its builds; mirror the one matching the bundled
   binary and ship it, or host it and reference it from the installer and
   About dialog.
3. Note that FFmpeg is used and where the source is, in the About dialog
   and the installer's licence page.

Alternative: ship an **LGPL** build of FFmpeg (gyan.dev and BtbN both offer
them). Then no source offer is needed for the binary beyond the LGPL's
(similar) requirements, but libx264 and libx265 disappear:

- Software H.264 would come from `libopenh264` (Cisco; BSD, and Cisco pays
  the MPEG-LA royalty for the binary *they* distribute, which does not
  extend to a binary you compile) or hardware encoders (NVENC / QSV / AMF)
  only.
- Software HEVC is not available in LGPL builds at all; hardware only.
- The recorder already prefers hardware H.264 for screen captures and falls
  back to libx264; that fallback rung and the converter's CPU presets would
  need an alternative.

Recommendation: keep the GPL build, do the compliance work in §4 items 1–3.
It is a day or two and does not reduce features.

## 5. Codec patents (lawyer)

Independent of copyright, H.264 (AVC) and H.265 (HEVC) are patented. Via LA
(formerly MPEG LA) licenses AVC; Access Advance and Via LA license HEVC pools.
For AVC there has historically been a royalty-free allowance for the first
100 000 units per year per licensee, but that requires enrolling as a
licensee. Practices in the small-ISV market vary widely (most small
converters ship FFmpeg and never enrol); a lawyer should advise on exposure
given expected volume and market. Hardware encoders do not remove the
question; the encoder patent licence is usually held by the GPU vendor for
*their* use, not the application's.

Formats without pool royalties: VP9, AV1 (AOMedia, royalty-free with patent
grant), Opus, FLAC, Vorbis, MJPEG, PNG/GIF. Offering these as defaults
reduces, but does not eliminate, exposure while H.264 remains selectable.

## 6. Work plan

### Phase 0: decisions (no code)

1. Ownership and Noldus relationship (§7 q1). **lawyer**
2. PyQt commercial licence vs PySide6 port (§3).
3. Company / trading name, product name, support address for the licence
   texts and installer.
4. Whether to sell per-seat, per-site, or subscription; this drives whether a
   licence-key mechanism is needed at all.

### Phase 1: clean the tree (1–2 days)

- Remove `Paradise.mp3` and `Never-Gonna-Give-You-Up-3.mid`; drop them from
  `NVC.spec`; make the easter egg silent or use a CC0 track with attribution
  recorded in `graphics/SOURCES.md`.
- Remove `team.png` from About or obtain written consent.
- Write `graphics/SOURCES.md` listing origin and licence of every image.
- Scrub personal names, machine names and paths from help screenshots
  (`docs/help`), CHANGELOG and BACKLOG.
- Rewrite history? Not needed for selling binaries, but if the repository is
  ever shared, the mp3/mid remain in history. Decide whether to `git
  filter-repo` them out.

### Phase 2: licence compliance (2–3 days)

- `THIRD_PARTY_LICENSES.md` in the repo and installed next to the executable:
  Qt (LGPL v3), PyQt5 commercial notice or PySide6 (LGPL v3), FFmpeg (GPL v3
  plus the per-library list from `ffmpeg -L`), Python (PSF), watchdog
  (Apache 2.0), requests/urllib3/certifi/idna/charset-normalizer.
- FFmpeg source: mirror the exact gyan.dev source tarball for the shipped
  build, host it, reference it in About and installer; or bundle it.
- About dialog: "Uses FFmpeg (GPL v3) — source at …", "Built with Qt / PySide"
  with links; drop anything implying Noldus endorsement unless §7 q1 says
  otherwise.
- Installer (Inno Setup, free for commercial use): EULA page, third-party
  licences page, uninstall leaves user data.
- Switch to PyInstaller **onedir** if not already, so Qt DLLs are
  replaceable (LGPL §4d).

### Phase 3: the PyQt decision, executed (0 days or 1–2 weeks)

- A: purchase licences, record licence numbers in a private file outside
  the repo, rebuild.
- B: PySide6 port on a branch, full suite green, Media Player re-verified,
  help screenshots regenerated.

### Phase 4: commercial plumbing (optional, 1–2 weeks)

- EULA text. **lawyer**
- Licence key or activation: only if the sales model needs it. A signed
  offline key (Ed25519 signature over customer + expiry, verified in-app) is
  a week of work and needs no server. Keep it out of the recorder's hot path.
- Privacy: the PC Report collects hardware, software, licence and network
  information. Sold software needs a privacy statement covering what is
  collected, that it stays local unless the user exports it, and the
  redaction option. GDPR applies if sold in the EU. **lawyer**
- Crash/usage telemetry: there is none; keep it that way or document it.
- Code signing certificate (EV or OV) so SmartScreen does not block the
  installer; ~€200–400/year.
- Trademark search on the product name. **lawyer**

### Phase 5: release hygiene

- Version scheme, signed installers, release notes derived from CHANGELOG.
- A support channel and a documented bug-report path that does not send PC
  reports by default.
- Keep `requirements.txt` pinned to exact versions for a release; record the
  FFmpeg build date and hash in the About dialog.

## 7. Open questions for the owner

1. **Who owns NVC?** It was written around Noldus workflows, stores settings
   under the "Noldus" organisation key and reads MediaRecorder presets from
   Noldus folders. If it was written during employment or on Noldus
   equipment, the employer may own it or have rights. This decides whether
   "sell" means a Noldus product, a licensed spin-off, or an independent
   product that must remove the Noldus name. **lawyer**, before anything else.
2. **PyQt licence or PySide6 port?** (§3)
3. **Ship GPL FFmpeg with source offer, or LGPL FFmpeg without libx264/x265?**
   (§4) Recommendation: GPL build plus compliance.
4. **Sales model**: per-seat, site, subscription, or free-with-paid-support?
   Determines whether Phase 4 is needed.
5. **Target market and volume** for the codec-patent conversation. (§5)
6. **Interoperability positioning**: is "reads MediaRecorder settings" and
   "controlled from The Observer XT" a feature to advertise (needs care with
   trademarks) or an internal convenience?

## 8. What does not need to change

- Running FFmpeg as a subprocess: already the right architecture for licence
  separation.
- Inno Setup: free for commercial use.
- PyInstaller: bootloader exception permits proprietary output.
- watchdog / requests: permissive; notices only.
- The test suite, translations and help are in-house work.
