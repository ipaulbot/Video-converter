# Recorder Preview And Settings Design

## Goal

Make the Multi-Source Recorder feel closer to MediaRecorder: previews should be smooth enough to use, synchronized when sources are recorded together, camera changes should refresh the main preview immediately, and recorder camera/output settings should persist across launches and named presets.

## Current Behavior

The recorder can now create separate files or one combined grid file. The final recordings are acceptable, but live preview is laggy because preview commands intentionally downsample streams to low frame rates and low width. Before recording, each source uses its own preview FFmpeg process, so camera panes drift out of sync. During combined recording, a single FFmpeg process produces the synchronized combined output, but the UI has to crop a lightweight preview stream back into individual panes.

Video Settings already edits multiple rows, but it only has OK and Cancel. Applying settings requires closing the dialog. Recorder settings live only in widget state and global app config; there is no MediaRecorder-style current settings file or named configuration file.

## Target Behavior

Use a balanced preview strategy:

- Idle preview uses individual camera preview processes with improved default preview quality.
- Recording separate videos keeps independent preview panes, but renders only the newest frame so the UI does not fall further behind under load.
- Recording combined grid uses one combined FFmpeg graph for output plus preview, then crops the preview into the visible source panes. This keeps the displayed panes synchronized with the combined recording without opening cameras twice.
- Preview quality is centralized so future tuning is simple. Defaults should be smoother than today without making recording unstable.

Use a MediaRecorder-like settings workflow:

- Add a `Video Settings` link below the recording properties table.
- Add an `Apply` button beside OK and Cancel in the Video Settings dialog.
- Apply updates source rows, output settings, and the main preview immediately without closing the dialog.
- OK applies and closes. Cancel closes without applying pending dialog edits.
- Changing source devices in the dialog and clicking Apply starts/restarts the affected preview pane.

Persist recorder configuration:

- Store current recorder settings in a JSON file under Public Documents/Noldus/NVC/MediaRecorder-style settings.
- Keep the JSON shape similar to MediaRecorder `.mrs` files but use clean NVC field names:
  - top-level version and output settings
  - timer settings
  - preview quality
  - list of channels
  - per-channel enabled state, video/audio names, source type, source text, frame rate, resolution, audio device, mute, volume, and RTSP settings when available
- Auto-save current settings when Video Settings is applied and when recording options change.
- Load current settings on recorder widget startup.
- Save named preset JSON files later using the same model; initial implementation can focus on `Current Settings.json` and a default path.

## MediaRecorder Reference Notes

The MediaRecorder help describes Video Settings as the place to select cameras, audio devices, frame rate, resolution, and output options. It notes that clicking OK returns to the main window and displays camera previews. It also documents Refresh Preview for cameras connected after opening the app, and Save Configuration As/Open Configuration using `.mrs` files. The `.mrs` examples are XML files with global output settings and repeated channel blocks. NVC should adopt the workflow and data concepts while using JSON for easier editing and safer parsing.

## Constraints

- Do not break the now-working separate and combined recording output modes.
- Do not open the same DirectShow camera twice while recording.
- Keep UI layout compact at the original window size.
- Do not store passwords in plain text in new JSON unless the user explicitly asks for credential persistence. RTSP URLs already in the source field may contain credentials and should be preserved as entered.
- Keep tests focused on command generation, widget behavior, and settings serialization.

## Verification

Automated tests should cover:

- Preview command defaults use improved FPS/width.
- Combined preview command remains a single FFmpeg process with a preview pipe.
- Video Settings Apply updates source rows and triggers preview refresh without closing.
- Video Settings link opens the dialog.
- Recorder settings serialize and restore output settings plus channels.
- Existing stop/finalization behavior still passes.

Manual verification should cover:

- Select two cameras, Apply, and confirm both previews appear without closing Video Settings.
- Record separate videos and confirm two files plus live preview.
- Record combined grid and confirm one file plus synchronized individual preview panes.
- Restart the app and confirm recorder settings are remembered.
