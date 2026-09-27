# NVC Change Log

Use this file to track user-visible fixes, improvements, and feature work.

## 2026-05-22

- Added browser-style output naming so converted files are not overwritten.
- Fixed HEVC CPU/GPU codec selection.
- Added output validation before reporting conversion success.
- Added unique GIF palette temp files.
- Hardened retention-day settings.
- Added PC report redaction for JSON and HTML exports.
- Added detailed HTML help documentation.
- Started stabilization work for tab layout, folder drop conversion, and preview theming.
- Added PC Report as a first-class tab.
- Added recursive folder drag/drop for supported media files.
- Added a Lossless Editor tab for FFmpeg stream-copy trim, remux, audio extract/remove, and merge.
- Added a first Multi-Source Recorder tab for up to four FFmpeg recording sources.
- Expanded PC report parity toward SIW with environment variables, codecs/MMC/sensors visibility, Noldus drivers, imaging devices, richer video, drivers, services, and process detail.

## 2026-09-03

- Put the project under version control, with a dependency manifest, ruff and
  pytest configuration, and a `conftest.py` so `python -m pytest` works with no
  environment setup.
- Fixed GPU encoder detection running a synchronous, un-timed `ffmpeg` probe at
  import time, which could hang startup before any window appeared. It is now
  cached and lazy.
- Added timeouts to every FFmpeg and FFprobe call, so a wedged binary can no
  longer freeze the window indefinitely.
- Replaced 125 silent exception handlers with logged ones. Set
  `NVC_LOG_LEVEL=DEBUG` to see the tracebacks behind an otherwise silent
  failure.
- Fixed scheduled deletions, unwritable configured folders, and a failed
  pending-deletion write all failing without any message.
- Fixed asset paths that resolved only because Windows filenames are
  case-insensitive.
- Replaced the hand-written help document with generated Help and Quick Start
  manuals, in PDF and DOCX, built from a single content source with
  screenshots. The Help menu opens the newest generated manual.
- Added a theme layer (`ui/theme.py`). The app's three visual states -- idle
  (teal), active (green) and locked (grayscale) -- are now named skins with one
  definition each, instead of the same colours repeated across four separate
  if/elif chains. Appearance is unchanged.
- Removed the superseded hand-written help document; the generated manuals are
  now the only help.
- Split the sidebar video preview, the easter-egg game and the conversion-queue
  bookkeeping out of the main window into their own modules, and added tests
  for the conversion worker. No user-visible change intended.
- Fixed closing NVC hanging after a conversion with a retention period set: the
  deletion timer was blocking interpreter exit for up to 30 days.
- Fixed two files with the same name in different folders writing each other's
  conversion log.
- The interface is now translatable: 367 user-facing strings are extracted into
  Qt catalogues under `translations/`. English is unchanged. Dutch and
  Simplified Chinese exist as draft catalogues awaiting translation, hidden
  unless `NVC_I18N_PREVIEW=1`. See `translations/README.md`.
- Moved the remaining stylesheet colours onto theme tokens. Changing the brand
  accent is now a single edit in `ui/theme.py`.
- Fixed the Settings dialog not showing its green active state while a
  conversion ran with monitoring stopped.
- Fixed a corrupted scheduled-deletion list silently stopping all retention.
  One malformed record used to block every pending deletion, permanently.
- "Check for Updates" no longer reports a fake update and no longer offers to
  open a placeholder download page. It now says update checking is not
  configured for this build. See `utils/update_checker.py` to enable it.
- Dutch and Simplified Chinese are now selectable from the Language menu,
  covering the core interface. Anything not yet translated shows English.
- The Info window now reports the real version and build date; it had been
  showing 2.1.160 / July 2025.
- Fixed the test suite reading and writing the real user's settings, which
  could change which tool tabs the app showed.
- Fixed NVC being able to abort on exit shortly after using the recorder. The
  terminate and kill escalations that follow Stop Recording were scheduled on
  timers owned by nothing, so they still fired 1.5 and 3 seconds later against
  a destroyed window; the same applied to the preview retry timers. They are
  owned by the recorder now and cancelled with it.
- Fixed the ffmpeg camera-mode probe that Video Settings starts when a camera
  is picked outliving both the dialog and the recorder. It is stopped on
  shutdown, and its result is discarded harmlessly if the dialog has since
  been closed.
- Fixed one unreadable row in the saved state discarding every high score.
- Added tests for the paths, resources, subprocess, system-state, log-bus and
  GPU-encoder helpers, which had none.
- Fixed the same class of unowned timer in the main window and the easter-egg
  game: the Converted-tab wiggle, the game launch three seconds after the
  intro, and the game's level transitions up to ten seconds out could all fire
  against a closed window. A source guard now fails the suite if a
  `QTimer.singleShot` is reintroduced anywhere.
- Dutch and Simplified Chinese now ship as they stand, without waiting for a
  native-speaker review. Both cover the core interface (146 of 365 strings);
  Qt shows the English source for the rest. A review pass is still worth
  doing, but it is no longer treated as a release blocker — an unreviewed
  Dutch or Chinese interface is better than an entirely English one.

## 2026-09-24

### PC Report

- Rebuilt on a section registry: 40 sections in NVC / Software / Hardware /
  Network groups, matching SIW's layout, each with a grouped Contents entry and
  a Top link. Sections collect in parallel; a failure in one section marks it
  partial instead of losing the report.
- Depth parity with SIW: operating system (activation, boot, policies), update
  history, licences, security (Defender, firewall, VBS, TPM, BitLocker),
  processes with owners, services, drivers by class, autorun with
  StartupApproved state, codecs across DirectShow/VCM/ACM/MFT, motherboard,
  BIOS characteristics, CPU caches and features, memory modules, sensors,
  devices, PCI, slots, adapters with advanced properties, video with corrected
  memory, monitors, sound endpoints, storage with partitions and reliability
  counters, logical disks, ports, USB, printers, VM detection, cameras (Frame
  Server, consent store, GenICam), network information, shares, connections.
- New Noldus Summary first: attention items (pending reboot, UAC, low disk,
  problem devices, USB selective suspend, Frame Server, camera consent,
  hasplms, jumbo frames), specs, Noldus software/drivers/filters/environment,
  cameras, dongles, GigE settings.
- Redaction extended: normalised label matching, IPs masked to two octets, MACs
  to the vendor prefix, hardware instance IDs, account names, SSIDs, DNS
  suffixes, proxy and UNC host names, personal device names; Name/Value rows.
- Admin-only fields show "Requires administrator" instead of failing; no UAC
  prompt.
- Report Health block: partial/empty sections, notes, elapsed time per section.
- The PC Report tab's progress text now names the section being collected and
  the running count.

## 2026-09-25

### Multi-Source Recorder

- Added per-source DirectShow audio selection, mute and volume control, including
  AAC audio for stream-copy video and automatic video-only retry when a selected
  microphone is unavailable. Without a microphone, file and RTSP (H.264 mode)
  sources keep their own sound track; Mute or Volume 0 records silent video.
- Recorder presets now load from and save to the MediaRecorder Presets folder,
  with Load, Set, Save as and Delete actions plus unsaved-change indication.
- Removed the non-functional Picture-in-picture choice, retained Separate videos
  and Combined grid, and made the recorder tab visible by default for fresh
  settings.
- DirectShow device names with accented or curly-quote characters are now listed
  correctly instead of as garbled text.
- Fixed "Refresh USB devices..." and "Refresh devices" in Video Settings
  appearing to freeze or do nothing. Device listing ran on the window's own
  thread (about 6 s per pass on a machine with ten DirectShow devices), the
  result was cached and never refreshed, and the combo box stayed on the
  refresh entry. Cameras and microphones are now found in a single background
  pass; the dialog scans automatically when opened, shows "Scanning..." and
  then a count ("2 cameras, 1 microphone found"), reuses results younger than
  45 s and rescans on demand with a refresh button. Picking the refresh entry
  restores the previously chosen camera.
- Every ffmpeg device-listing process is now tracked and terminated when the
  recorder shuts down or the application exits. Previously a listing that
  outlived its parent stayed behind; hundreds of such processes were found on
  a development machine, all waiting on DirectShow enumeration, which made
  every later scan time out with an empty device list.
- The recorder's layout schematic in the sidebar is drawn on a transparent
  canvas with white tiles, so its dashed leaf frame looks like every other
  tab's preview instead of a black block.
- "Video Settings" and "Show recording log" links carry gear and list glyphs;
  each camera's settings button is a camera glyph; the rescan control is a
  refresh glyph. All follow the locked/active accent like the other icons.
- Fixed Combined grid failing to record ("Recording failed") with an Axis camera
  that rejects the `?resolution=…&fps=…` request options. Separate videos had
  always retried without those options; the single combined process did not.
  It now steps down the same ladder (full options, then without the frame
  rate, then without any requested option). The combined process also opens
  USB cameras in their configured frame rate and resolution instead of the
  driver default.
- Picture-in-picture is back as an output mode and records: source 1 fills a
  1280×720 frame and the other enabled sources are insets along the bottom
  left, matching the layout schematic in the sidebar. Presets saved with this
  mode load as Picture-in-picture again.
- New Screen capture source type. Leave the address empty (or `desktop`) for
  the whole screen, enter `monitor=1` (or pick "Screen capture (monitor 1,
  GPU)" in Video Settings) to record one display through the GPU, or enter a
  window title to capture one window. It records at the row's frame rate
  (15 fps when set to Auto), is always encoded to H.264, previews like a
  network stream, and can be mixed with cameras in Combined grid or
  Picture-in-picture. The Video Settings device list offers the whole
  desktop plus one GPU entry per attached display.
  - The GPU mode uses the Desktop Duplication API, so DirectX content is
    captured and a 4K display costs no CPU; if it cannot start (no D3D11
    device, a remote session, a display that is no longer attached) the
    recording falls back to a GDI grab of the whole desktop.
  - Screen recordings are encoded as 4:2:0 H.264 with even dimensions. The
    grabbers deliver BGRA, which libx264 otherwise encodes as 4:4:4 — a
    file the Windows players and hardware decoders refuse to play.
  - Configured like an RTSP camera: pick the single "Screen capture" entry
    in the Video Settings device list, then the gear opens Screen Capture
    Settings — whole desktop, one display (GPU), one window (a live list of
    open windows, minimised ones included, with Refresh — or type a title),
    or part of the desktop (X/Y/W/H, or "Select on screen..." which dims
    every monitor and lets you drag out a rectangle; Escape cancels). The
    device box then reads "Screen capture (desktop | monitor N, GPU |
    window: title | region X,Y WxH)". Regions are virtual-screen pixels; a
    monitor left of the primary one has negative X. The row's address
    accepts the same by hand: `desktop`, `monitor=2`, `region=X,Y,WxH`, or
    a window title.
  - Screen captures use the GPU's H.264 encoder when one works here. While
    listing devices, NVC tries NVENC, Quick Sync and AMF in turn on a
    two-frame synthetic clip and remembers the first that starts (the log
    shows "[encoder] screen captures will use h264_nvenc"). Cameras keep
    their current encoding. If the encoder refuses a real recording (Quick
    Sync, for one, will not take a 5120-pixel-wide desktop) the recording
    restarts with libx264 on the same capture.
- The "Medialooks Screen Capture" DirectShow filter installed by MediaRecorder
  is no longer offered as a camera. Its licence check pops a modal dialog
  inside FFmpeg the moment it is opened, leaving the recording stuck behind
  the dialog. A preset that still names it loads as the built-in screen
  capture, with a log line saying so.
- NVC can be driven from the command line the way MediaRecorder is driven by
  `MRCmd.exe`, so The Observer XT's external-application entries work with
  `NVC.exe` as the program: `/E` launch or bring to front, `/R` start
  recording, `/S` stop, `/X` close, `/C=<preset name or .json path>` load a
  video preset, `/B=<name>` set the file base name. Switches combine
  (`NVC.exe /E /C=Lab1 /R`) and run as preset, base name, record, stop,
  close. A running NVC receives the request over a local pipe and answers;
  the calling process exits 0 on success and 1 with the reason (locked,
  converting, preset missing, no source enabled) on the console and in the
  conversion log. With no NVC running, `/E /R /C /B` start it first; `/S`
  and `/X` have nothing to do. `/?` shows the switch summary.
- Fixed "Select on screen..." in Screen Capture Settings showing an overlay
  that could not be clicked until both settings dialogs were closed. The two
  dialogs are modal and Qt sends input only to the newest modal window, so
  the overlay is now modal itself. While it is up the two dialogs turn
  transparent so they do not cover the area being chosen, and a banner reads
  "Drag to select the area to record. Press Esc to cancel."
- Fixed "Start Recording" staying green after a recording was stopped. The
  button's style was rendered before the theme was told the recording had
  ended, so it always showed the previous state's colour. The tab underline
  now also turns green while recording, as it already did during conversion.

### Main window

- Fixed the burger menu icon being cut off at the bottom: the button was
  taller than the tab-bar corner it sits in. It is now sized from the tab bar
  in both window modes.

### Media Player

- Added volume and mute for all panels, fullscreen (F / Esc / double-click, auto-hiding
  transport bar), and keyboard shortcuts: Space, Home, Left/Right frame step,
  Shift+Left/Right 5 s, Up/Down volume, M, F, N/P.
- Frame-accurate stepping using the clip's real frame rate (ffprobe), with a
  H:MM:SS.mmm and frame N / total readout.
- Per-panel playlist (add files or a folder, reorder, drag from Explorer); auto-advance
  only in single-panel mode.
- Converted Files gains "Play in Media Player" (context menu and Play button); the tab is
  shown for the session even if hidden in settings.
- Files Windows cannot decode show an inline "Convert to MP4 (H.264) and play" offer
  instead of a blank tile.
- Fixed: MP4, MOV and MKV files now play. The player previously ran on Qt's DirectShow
  backend, which cannot demux those containers on a stock Windows 10 install (only AVI
  and WMV worked). The app now selects the Media Foundation backend at startup and
  creates the player without the `VideoSurface` flag, which that backend rejects.
- Player settings (last folder, panel count, volume, mute) persist between sessions.
- Fixed an access violation when a player that had loaded a clip was shut down
  and destroyed while the event loop kept running (seen in the test suite; the
  same sequence applies when the tab's widget is torn down in the app). The
  Windows media backend finishes closing a session asynchronously; shutdown
  now lets those events land before the player is destroyed.

### Settings

- The four folder "Change" buttons carry a folder glyph and are wide enough
  for glyph plus label.

### Help documentation

- Rewrote the Help manual against the current application: every Settings tab,
  the seven main tabs and their default visibility, Converted Files, Time
  Restrictions, Language, Updates and Logs.
- New Media Player chapter (controls, shortcut table pinned by a test, fullscreen,
  playlist, unsupported-format fallback) and a rewritten Multi-Source Recorder
  chapter built around the Video Settings dialog and presets.
- PC Report chapter lists every section in report order and describes the
  always-on redaction and administrator-only fields.
- Quick Start gains "Record From a Webcam" and "Review a Recording".
- Two new figures (Media Player, Video Settings); all figures recaptured with
  stand-in device names and paths, and captions corrected to match what is shown.
  Regenerated the 2.3.0 PDF and DOCX manuals; the README names the 2.3.0 files.

### User interface

- Two window modes from the burger menu, Window > Compact mode (1024x640, the
  former default look) and Full window mode (maximised). The choice persists;
  tool tabs re-flow for each mode.
- Every tool tab sits in a "leaf" card (rounded top-left and bottom-right
  corners, square elsewhere); the drop zone and preview box use the same shape.
- Button hierarchy: the gradient bubble is reserved for the primary actions
  (Start/Stop, Settings bar). Tool tabs use small filled buttons, text links and
  flat glyph icons instead of a uniform bubble.
- Compact mode fits all seven tool tabs in the tab bar without scroll arrows; a
  narrower window elides tab titles rather than hiding tabs.
- PC Report: hint paragraphs removed, heart pulses under the logo while a report
  runs and stays lit when it finishes, Open report / Open folder are links, and a
  "Run as administrator" link relaunches NVC elevated for the admin-only fields.
- Media Player: icon transport bar (play/pause, stop, restart, fullscreen,
  playlist, mute), icon Load/Clear per panel and an icon playlist dock; fixes
  clipped buttons in narrow windows.
- Lossless Editor: compact tool row, icon Add/Clear on the merge list header,
  end time placeholder "end of file".
- Multi-Source Recorder: Output settings sit to the left of Recording
  properties in both modes; the file location field is capped in width and
  shows the tail of long paths with an icon Open button; the Video/Audio name
  columns take the spare width and the preview tiles grow taller; a note
  explains that USB cameras are always re-encoded when "copy" is selected.
- The title bar offers Maximize/Restore again; using it switches between Full
  window and Compact mode without forcing the window back to 1024x640, so a
  Full window can be restored and dragged to any size.
- Grey blocks behind tab headings, group boxes and labels (Media Player,
  Multi-Source Recorder, Video Inspection Tool) are gone: only the window and
  dialog surfaces are grey, everything on a leaf card is white.
- More glyphs: PC Report's Open report / Open folder / Run as administrator
  links carry report, folder and shield icons that follow the skin; the
  Lossless Editor's Browse is a folder icon button.
- Video Settings: Output quality now changes the recording (Default veryfast/18,
  High medium/16, Balanced veryfast/20, Compact faster/24) and is saved with
  presets; "Use maximum recording time" is bound to the tab's Timer; the unused
  Time format / Decimals controls are gone.

### Fixes

- Converted Files: Clear button appears once the table has rows (it was never shown).
- Per-file conversion logs honour Settings > Folders > Log Folder.
- pyproject.toml version matches the application (2.3.0); a test keeps them in sync.
- Help opens the manual for the saved interface language.
- PC report Noldus Summary reports wall-clock collection time separately from
  the time summed across parallel sections (previously "370 s" for a 91 s run).
- Recorder test no longer depends on a webcam being attached.
- Media Player: leaving fullscreen no longer leaves the tab sized to the clip's
  native resolution (a 1080p clip grew the video area past the window).
- The layout tests no longer write `window_mode` into the real config.json.

## 2026-09-26

### Main window

- Fewer tabs. Conversion Log and Converted Files are now one **Video Converter**
  tab: the files table sits above the conversion log with a draggable divider,
  and the tab has a single footer (the broom clears the log; Clear empties the
  table). The Video Inspection Tool tab is gone; its inspector lives in the
  Media Player (below). Settings -- Tools shows one toggle per remaining tab
  (Video Converter, Media Player, Multi-Source Recorder, Lossless Editor, PC
  Report); Video Converter, Media Player and the recorder are on by default.
- Existing settings migrate: `conversion_log` / `converted_files` collapse into
  `video_converter` (on if either was on); a visible `video_inspection` turns
  the Media Player on. Unknown keys are dropped as before.
- The BallBuster easter egg hides the files table while it plays and restores
  it afterwards, so the game gets the whole tab.

### Media Player

- **Inspect** panel: a magnifier button on the transport bar (next to Playlist)
  opens the ffprobe inspector beside the video, in the space the playlist uses.
  It shows the Summary and Detailed JSON for the selected panel's clip and
  follows panel selection and loads; dropping a file on it inspects that file
  without loading it. Playlist and Inspect share the slot, so one closes the
  other.
- Converted Files gains an **Inspect** button and an "Inspect in Media Player"
  context-menu action, which open the player on that file with the Inspect
  panel showing (the tab is shown for the session even if hidden in settings).
- Help: Main Window Overview, Converting Files, the Converted Files and Media
  Inspection chapters, and figures FIG-03 / FIG-04 updated for the new layout.
- Second pass the same morning: the Inspect panel is **open by default** and
  sits in a splitter beside the video, so it keeps its share of the window
  instead of staying a fixed strip when the window is maximised; the dashed
  drop frame around the text is gone (plain panel, real scroll bar). The
  **Playlist** is now a strip under the video, independent of Inspect (both
  toggles remembered between sessions; panel count no longer opens it).
  Fullscreen hides both and restores them on exit.
- A clip shows its **first frame as soon as it is loaded** (the tile reads
  "Loading..." for a moment), and the seek slider moves the picture before
  the first Play. Previously the tile stayed black until Play and paused
  seeks did nothing, so a dropped file did not look loaded.
- The sidebar preview follows the player's selected clip again (it used to
  follow the Video Inspection Tool). Whether that preview stays is a backlog
  question.
- Fixed a possible abort at exit: an ffprobe inspection still running when
  the inspector was destroyed took the process down ("QThread: Destroyed
  while thread is still running"). The probe is now killed and joined on
  shutdown.

### Multi-Source Recorder

- RTSP camera "not loading": the address on this machine's saved row had a
  four-digit octet, which ffmpeg treats as a host name and tries to resolve,
  so the preview reconnected forever with only a log line. The RTSP/IP
  Camera dialog now refuses an Address that looks like an IP but is not one,
  and a stream preview that dies with "Failed to resolve hostname" reads
  "Cannot resolve the camera address / Check the IP in Video Settings" and
  stops retrying until the source is edited.

### UI polish batch (later the same day)

- **One header on every tab.** Each tool tab now opens with the same
  three-part header: a runtime-painted glyph (a magnifier with an eye for the
  Media Player, an arrow cycle around a play symbol for the Video Converter,
  a camera for the recorder, scissors for the Lossless Editor, a monitor for
  PC Report), the tab's title and a one-line description. The Video Converter
  tab, which had no header, gets one; PC Report keeps its heart as a layer
  under the glyph. Headers follow the accent colour.
- **Drag tabs into any order.** Tabs are movable; the order persists as
  `tool_tab_order` in settings and is restored at start.
- **Empty lists show their intent.** The Converted Files table and the
  player's playlist paint faint grey bars, fading down the empty area, until
  the first row arrives.
- **Full window -> compact no longer jitters.** The whole mode switch (tab
  re-flow, tab restyle, restore, resize, centre) happens with repaints held,
  so it lands in one frame instead of half a second of resizing panels.
- Video Converter right-click menu: on empty space, **Add videos to
  convert...** and **Monitor a folder...**; on a row, additionally **Monitor
  this file's folder** and an **Open in** submenu (Media Player, Lossless
  Editor, Default app). Monitoring a folder sets the Source Folder and
  restarts a running watch.

### Media Player (polish)

- The "Inspect - Panel N: ..." title row above the inspector is gone; the
  panel caption already names the clip.
- Every clip loaded into or dropped onto a panel is **added to that panel's
  playlist** and selected there, so the strip shows what the panel has seen.
- Leaving the Media Player tab and coming back no longer leaves the paused
  tile blank: the panel re-presents its frame (Media Foundation drops the
  presented picture when the surface is hidden) at the same position,
  muted while it does so.
- The per-panel **offset spin box moves into the playlist** as an
  **Offset** column (Clip | Offset). Double-click the cell to edit the sync
  shift in seconds; a paused panel showing that clip moves at once. Drag
  reorder of playlist rows is kept.

### Multi-Source Recorder (polish)

- Output settings and Recording properties now sit **top-aligned** (the
  shorter group used to hang lower), the Output settings fields share one
  width, and the group is capped at 380 px.
- Preview tiles **grow to fill the tab**, so Full window mode no longer
  leaves most of the screen empty under four small tiles.
- **Video Settings dialog is narrower** (about 990 -> 810 px at default
  fonts): the Audio device column is capped and elides long device names
  (the full name is in the tooltip), the Video device column takes the spare
  width, and the preset **Save as... / Delete** buttons became quiet grey
  text links so the eye is not pulled to them.

### Docs

- Help: Main Window Overview (headers, movable tabs), Converted Files (new
  menu items, placeholders), Media Player (playlist behaviour, Offset
  column), Multi-Source Recorder (Video Settings audio names, preset links).
- Planning: `docs/planning/2026-09-26-product-naming-website-and-github.md`
  records the landing-page site, the shared product voice / rename question
  ("Media Multitool" argued against; short proper name + descriptor argued
  for) and the GitHub presence steps. Planning only; nothing renamed.
- Test hygiene: a `_FakePlayer` helper had been indented inside a test
  class, which silently un-collected six Media Player tests; they run again.

### Follow-up pass (12:04)

- List placeholders are now **thin hairlines** under every empty row slot,
  all the way down the view (the look of an old spreadsheet grid), instead
  of fat, rounded, fading bars.
- The **Multi-Source Recorder and Media Player headers line up** with the
  other tabs: both widgets dropped their own outer layout margins (6 / 16 px)
  and the header glyph is top-aligned so a wrapped description cannot push
  it down. The player's description is shorter so it stays on one line.
- Media Player playlist gains a **Panel** column listing the panels showing
  each clip; it appears only when more than one panel is on screen.
  **Highlighting a playlist row shows that clip's ffprobe details in
  Inspect** without loading it, and a click on the video surface itself now
  selects the panel (the native surface used to swallow the press), so
  clicking a video shows its codec info too.

### Follow-up pass (14:18)

- **Recorder tab crept downwards with one source.** Each preview frame was
  scaled to the tile's current size, and a QLabel's size hints follow its
  pixmap, so every frame asked the layout for 2 px more (pixmap + frame),
  got it, and the next frame was scaled 2 px taller -- until Output settings
  and Recording properties needed scrolling. Tiles now have fixed size hints
  (the layout alone sizes them) and frames are scaled to the content rect.
- List placeholders: the hairlines break at the column boundaries and stop
  8 px short of the view edges.
- Video Converter list: the green Clear / Play / Inspect push buttons are
  gone. Play and Inspect are quiet 24 px glyph buttons under the table's
  right edge (still only when a row is selected); Clear is the footer broom,
  which now empties the file list together with the log (the footer's file
  button already adds videos). The selected row's text is readable again.
- Two stray grey shapes fixed: the table's row-number column drew a rounded
  box down the left (a `QFrame` style rule on the container leaked onto the
  header; the header is hidden and the rule is scoped), and the splitter
  handles above the log and beside the player's Inspect panel painted as
  grey bands (now transparent, still 8 px to grab).
- The Media Player playlist and the Lossless Editor merge list wore Qt's
  near-black frame; both now use the same thin grey border as the other
  boxes (`theme.list_box_style()`).
- **Media Player: a paused clip could quietly run on.** With the Windows
  Media Foundation backend, a seek issued while paused sometimes plays at
  full rate (with sound) although the player still reports Paused -- seen
  when scrubbing right after a load, and when the re-presented frame on a
  tab return did play -> pause in one go. The first-frame nudge now waits
  for the pipeline to move before pausing, and every paused seek is watched
  for about a second: if the position keeps advancing, a short muted
  play/pause round trip pins the frame back at the requested spot (at most
  three tries). Reproduced 4 times out of 5 with a probe before the fix,
  0 of 8 after.

### Follow-up pass (15:32)

- **Workflow rules, written down and applied** (`ui/workflow_rules.py`, spec
  `docs/superpowers/specs/2026-09-26-workflow-rules-and-player-responsiveness-design.md`).
  Switching tabs never stops or pauses anything and no tab is ever greyed out
  (the old "recording locks every other tab" is gone). Recording is exclusive
  with the other ffmpeg jobs: while a recording is starting, running or
  stopping, the converter's Start reads "Recording..." and the Lossless
  Editor's job buttons are greyed out, each with the reason as tooltip. A
  conversion or the folder monitor blocks Start Recording only; the rest of
  the recorder stays usable (it used to be disabled wholesale). Media Player
  and PC Report are never blocked.
- **One status line on every tab.** The five footers each had their own
  label and three of them were never written. Every footer now shows the same
  `Status: ...` line listing what runs (Recording · Converting · Monitoring,
  Locked first), "Idle" when nothing does; the dot is green for a running
  job, amber for the monitor alone, red after a failed recording, grey when
  locked.
- **Media Player: a drop on the second panel showed nothing.** The playlist
  strip and Inspect follow the *selected* panel and a load did not select.
  Now any load -- drop, Load button, playlist -- selects its panel first, so
  the strip switches to that panel's list and Inspect shows the clip.
- Media Player: Panels, Speed and Volume moved left to sit with the other
  controls (three groups: transport, view, playback settings).
- Media Player: the Inspect dock was a white void until something was
  inspected; the Summary / JSON pane now wears the grey list-box border while
  empty (and the text panels inside dropped their own border).
- **Media Player: compact window cut the Inspect dock off.** Reproduced: the
  panel captions were plain QLabels whose minimum width is their whole text,
  so two long clip names pushed the tab past the window and behind a
  horizontal scroll bar. Captions now elide in the middle (`ElidedLabel`,
  full name on hover); the tab's minimum width no longer depends on file
  names.
- Media Player: the native video surface is hidden while its panel is hidden
  and shown again with the re-presented frame, so a tab switch cannot show
  stale screen content (the converter table, in the report) in the tile.
  Not reproducible headless -- see BACKLOG for the follow-up if it persists.

### Follow-up pass (16:14)

- Media Player: the "Playlist - Panel N" title row above the playlist is
  gone (the panel name stays as the list's tooltip) and the first column is
  headed "File Name", matching the Video Converter table.
- **Dutch and Simplified Chinese UI catalogues complete**: 462 of 462
  strings translated in `translations/nvc_nl.ts` / `nvc_zh_CN.ts`, `.qm`
  files rebuilt. Fixed on the way: `build_translations.py` dropped the blank
  line inside strings that contain a paragraph break (`"\n\n"`), so eight
  dialog texts could never match at runtime; the `.ts` writer now uses
  `ElementTree.indent` and a round-trip test guards it.
- **Dutch and Simplified Chinese manuals** (Help and Quick Start Guide, PDF
  and DOCX; `docs/help/source/locales/nl`, `locales/zh_CN`). New
  `doc_strings.py` localises the builder's own words (Contents, Note,
  Figure N., missing-figure text, document titles) and `manual_fonts.py`
  embeds Microsoft YaHei from the Windows font folder for zh-CN (fallback
  chain, then the STSong-Light CID font). The PDF wrapper now breaks
  spaceless CJK text per character with hanging punctuation, so Chinese
  paragraphs fill the measure. File names keep the English titles because
  the in-app Help menu looks manuals up by title and falls back to English.
- English Help updated for Picture-in-picture, screen capture, the Language
  setting and the current Media Player (File Name / Panel / Offset columns,
  Inspect panel); glossary entries for Picture-in-picture and Screen capture.
  The Settings -- Folders -- Log Folder text no longer says the field has no
  effect: it now points per-conversion logs at the chosen folder.
- **Help figures re-captured** without touching the display: the capture
  script parks every window off-screen and only ever calls `widget.grab()`.
  Recorder widgets are built with previews off for the run, so the
  operator's saved cameras and screen-capture sources are never opened; the
  FIG-07 tiles receive ffmpeg test patterns through the widget's own frame
  path. The Media Player's native video tile (black to `grab()`) gets the
  frame ffmpeg extracts at the paused position composited in. The FIG-08
  clip lives in the Public Videos folder for the duration of the run, because
  the Inspect panel prints its full path. All 12 manuals regenerated.

### Follow-up pass (18:16)

- **Recorder: previews really stop.** `QProcess.terminate()` is `WM_CLOSE`
  on Windows and `ffmpeg.exe` has no window, so an unchecked row's preview
  kept running -- camera light on -- after the widget had already forgotten
  it. Previews are now ended with `kill()` (they write JPEGs to a pipe and
  have nothing to flush; `stop_preview_processes` also loses its 1.5 s
  blocking wait). A row that stops describing a previewable source (USB
  camera with "No source selected...", a file, a plain URL) now stops the
  preview it had before, so the desktop capture no longer lingers in the
  tile. Choosing "USB / DirectShow" no longer pre-fills the first known
  camera: "No source selected..." means no camera, and the tile says
  "Configure the source" until one is picked.
- **BallBuster keeps its pace at any window size.** Every frame rescaled the
  background and every ball with smooth transformation (and re-read the halo
  PNG from disk); at 1920x1080 a paint took ~20 ms while the 16 ms loop
  advanced one fixed step per tick, so the game ran in slow motion. Scaled
  pixmaps are cached per size and the loop now runs as many 1/60 s steps as
  real time elapsed (capped at 4), so ball speed is pixels per second.
  While the game runs, the Video Converter header becomes a ball glyph +
  "BallBuster XT" + a one-line joke; leaving the game restores it.
- **Portfolio site started** as a separate repository
  (`D:\Python Projects\portfolio-site`): a static one-page site plus resume
  generated from a single `content.py`, with NVC and Virtual IO Box project
  cards using the clean help-figure screenshots. Identity, contact and resume
  facts are placeholders the build lists until filled in. Design note:
  `docs/superpowers/specs/2026-09-26-portfolio-site-design.md`.
- The 2.3.0 exe build is deferred to tomorrow at the owner's request.

## 2026-09-27

### Follow-up pass (18:20)

Design note: `docs/superpowers/specs/2026-09-27-sidebar-context-panel-and-tools-design.md`.

- **Sidebar is a context panel.** The per-tab headers are gone; one compact
  header under the logo shows the current tab's glyph, title and one-line
  description (three lines are reserved so the preview box below does not
  hop between tabs). BallBuster borrows it while the game runs. The
  "Current Video Settings" text is gone from the sidebar.
- **Current Video Settings is a table in the Video Converter tab**, beside
  the log under the files list: Format, Video codec, Audio codec,
  Resolution, Bitrate, Frame rate, plus Time window and Mode (Copy only)
  when set. Clicking it opens Settings -- Format, as the old text did. The
  game hides it with the files table; the game's score, high score, level
  and best level now run in the converter status line.
- **Hide and show tools.** Right-click a tab for "Hide <tool>"; Menu -- Tools
  lists every tool with a check mark and a "Show all" entry. Both write the
  same `visible_tool_tabs` setting the Settings -- Tools tab uses. Hiding the
  current tab selects the nearest visible one; the last visible tool cannot
  be hidden (its entries are greyed).
- **Leaf-shaped preview stays leaf-shaped.** The sidebar preview label paints
  its pixmap (thumbnail, decoded frame, recorder schematic, star field)
  clipped to the leaf outline, so a loaded or playing video no longer
  squares off the rounded corners. The idle box is blank instead of reading
  "No Preview".
- **PC Report heartbeat.** While a report runs, a red heart pulses in the
  sidebar leaf (0.9-1.1x on a 900 ms cycle), only while the PC Report tab is
  current; the header heart layer is removed with the header. `PCReportWidget`
  announces `report_running(bool)`; the main window relays it to
  `PreviewController.show_heartbeat`.
- **Media Player: one playlist for all panels.** Every panel's loads land in
  one shared list; the Panel column says where each clip is showing;
  double-click loads into the selected panel; N / P walk the shared list from
  the selected panel's clip. The strip is capped per window mode
  (`playlist_strip_h`: 92 px compact, 150 full) and compact panels are 136 px
  (16:9 at their width), so compact mode no longer scrolls with the playlist
  open.
- **Recorder: row 1 is an ordinary row.** Its Use box can be unticked in the
  Video Settings dialog and on the tab. With no row enabled the recorder's
  Start is disabled and the status reads "Enable at least one source".
- i18n: 23 new strings translated in nl and zh-CN (catalogues 474/474, .qm
  rebuilt). Help: Main Window Overview, Settings -- Tools, Media Player
  playlist and recorder Video Settings updated in all three languages.

### Follow-up pass (19:10)

- **Recorder keeps its video area with no source enabled.** Unticking every
  row used to collapse the preview grid and shove the Output settings and
  Recording properties groups up the tab. One black tile now spans the grid
  reading "No source enabled / Tick Use on a source to preview it"; the
  groups stay where they were.
- **Sidebar header: glyph beside the title, description left-aligned.** The
  compact `TabHeader` puts the glyph and title on one line (title at 16 px so
  most fit beside the glyph) and wraps the description underneath, ragged
  right instead of centred. `TabHeader.reserve_for()` measures every heading
  the sidebar can show (all five tools plus BallBuster's) and fixes the
  title and description heights to the tallest, so switching tabs never
  moves the preview leaf (verified: same leaf y on every tab).
- i18n: the recorder tile string translated in nl and zh-CN (475/475, .qm
  rebuilt); help Main Window Overview and recorder Video Settings updated in
  all three languages.
