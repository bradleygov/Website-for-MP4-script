# Ops Command Center (dashboard source)

Source for the "Bradley Ops Command Center" Claude artifact dashboard.

- `index.html` — page markup, styles and draw scripts (two-column layout, filter tabs, color-coded category cards).
- `data/*.json` — **sample** datasets (projects, reno tasks, printer fleet, Brookfield milestones, n8n log, BNPL plans, budget).

To go live, replace each JSON file with real exports (e.g. an n8n workflow that writes
`GET /api/v1/executions` output to `n8n_log.json` on a schedule) and re-upload it to the dashboard.
