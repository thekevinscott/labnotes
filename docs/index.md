---
layout: home

hero:
  name: 'labnotes'
  text: 'Experiments in the folders you already have'
  tagline: 'Run param sweeps, watch them live, and keep your notes next to the results. No server to host, no database, nothing to sign up for.'
  actions:
    - theme: brand
      text: Get Started
      link: /getting-started
    - theme: alt
      text: Philosophy
      link: /philosophy

features:
  - title: Plain files
    details: Experiments, notes and runs stay as folders on your disk. A .labnotes.toml maps them to your layout, whatever it is.
    link: /common-organizations
  - title: Run from the terminal
    details: Define params and repeats in experiment.toml. A live table lets you reorder, deselect, retry and change concurrency while runs go.
    link: /cli/experiments
  - title: Read in the browser
    details: Sort and filter runs, follow a run's output, and write notes with Python blocks that run in place.
    link: /frontend
  - title: Drive it with an agent
    details: The skill lets Claude Code or Codex set up experiments, start runs and answer questions about them.
    link: /skill
---
