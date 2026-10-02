# The dashboard

```text
hone-frame dashboard --home ./studio --port 8792
```

A local page (standard-library server, no build step) over the same workspace, with a runner thread
that executes queued runs one at a time and resumes interrupted ones on start (design §12).

| View | What it is for |
|---|---|
| Overview | four real metrics (images today, queued and running, median render time, GPU time), the live queue, recent images |
| Create | a task, its subjects and presets, profile and selection settings; the plan with every output, model and reference before you press Generate |
| Library | Characters, Environments, Assets and Images, with details, history, import and "use as reference" |
| Scenes | the scene builder: references with roles, camera, expression, pose and lighting, then drafts, finals and promotion |
| Sheets | the composer and saved sheets, exported with their originals |
| Queue | every run, and the run page: stages, the current task round by round, the judge's checks, live activity, pause / cancel / resume / retry, manual picks |
| Presets, Models, Settings | the catalogue, what hone-models offers, project defaults and the theme |

The page shows only real data: a metric with nothing measured is "—", an estimate without evidence is
"Estimating". It binds to `127.0.0.1` and has no accounts. Images are served only from a project's
`images/` and `sheets/` folders, as images, never as script.

From Python: `from hone_frame.dashboard import Dashboard, serve`, then `serve(ws)`, or
`Dashboard(ws, port=0).start()` in tests.
