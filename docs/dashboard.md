# The dashboard

```text
hone-frame dashboard --home ./studio --port 8792
```

A local page (standard-library server, no build step) over the same workspace, with a runner thread
that executes queued runs one at a time and resumes interrupted ones on start (design §12).

| View | What it is for |
|---|---|
| Project | the brief and style, the next step, the characters with their progress, the world, the scenes, what is running; **Generate assets** makes the world's places and objects |
| Characters | each character's page: the hero and details, **Generate assets** (every pack, with your own items), a section per pack (hero, turnaround, expressions, poses, outfits, states, actions) with **Regenerate** and **Add**, each image's candidates with **Use this one** and **Generate again**, the belongings, and the model sheet |
| World | places and objects anyone in the story can use; add, edit, **Generate assets** |
| Scenes | the scene builder: characters, places and objects with roles (the planner adds the belongings the description needs, marked "suggested"), camera, expression, pose and lighting, then drafts, finals and promotion |
| Queue | every run, and the run page: stages, the current task round by round, the judge's checks, live activity, pause / cancel / resume / retry, manual picks |
| Presets, Models, Settings | the catalogue, what hone-models offers, project defaults and the theme |

All images, Sheets and the generic Create page are linked from the project page.

The page shows only real data: a metric with nothing measured is "—", an estimate without evidence is
"Estimating". It binds to `127.0.0.1` and has no accounts. Images are served only from a project's
`images/` and `sheets/` folders, as images, never as script.

From Python: `from hone_frame.dashboard import Dashboard, serve`, then `serve(ws)`, or
`Dashboard(ws, port=0).start()` in tests.
