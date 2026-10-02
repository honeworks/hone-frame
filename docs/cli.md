# The command line

Install the `cli` extra (`pip install "hone-frame[cli]"`). Every command takes `--home DIR` (default
`$HONE_FRAME_HOME`, else `~/hone-frame`). The ones that print take `--json`. Exit codes: 0 success, 1
a hone-frame error, 2 a usage error.

```bash
hone-frame presets --category camera
hone-frame presets --json > presets.json
hone-frame projects --home ./studio
```

```text
hone-frame dashboard [--port 8792] [--no-runner]   serve the dashboard (and run the queue)
hone-frame run-queue [--once]                      run queued runs in this process
hone-frame status PROJECT RUN_ID                   one run: status, progress, outputs
hone-frame export-pack PROJECT SCENE_ID OUT.zip    a scene's reference pack
```
