# Research notes

What we learned while building hone-frame: experiments on the real models, web research, tools we
might use, and ideas waiting for a design. These notes are **not the design**: the design is
[`../current.md`](../current.md) and the change records in [`../changes/`](../changes/). An idea here
becomes real only through a change record that the owner accepts.

| File | What it holds |
|---|---|
| [`prompting-findings.md`](prompting-findings.md) | how our image models respond to prompts: language vs tags, culture and period, prompt length, edits that keep the pose, mannequins, casting, the judge |
| [`root-causes-2026-10-03.md`](root-causes-2026-10-03.md) | the root cause analysis of the first full two-variation world (Rostam and Sohrab v2) |
| [`tools-and-libraries.md`](tools-and-libraries.md) | open-source models and Python libraries that could help each stage, with license, memory and status |
| [`ideas-backlog.md`](ideas-backlog.md) | every idea and owner decision not yet built, with its status and what it depends on |

How to add to these notes:

- Date every experiment, name the models and versions, and say where its images are kept (they live
  outside the repository, in the owner's lab folder `~/hone-frame-lab/`).
- Say what was measured or seen, not what was hoped. A negative result is worth writing down.
- When an idea is designed, link its change record from the backlog and mark it `designed`.
