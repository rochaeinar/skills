# CLAUDE.md

Monorepo of static app websites (Astro, npm workspaces), one site per subdomain, deployed to Cloudflare Pages on several Cloudflare accounts. Use the `cloudflare-site` skill for every task here (new site, analysis, assets, build, deploy, domains): its `SKILL.md` has the workflow and rules.

- One site = `sites/<slug>/`, described by `site.json` (`profile` = which Cloudflare account). Shared components in `packages/ui/src/`.
- Texts live in `src/i18n/<lang>.json`; every claim about an app must be verified in the app's code (`content/analysis.md` records the evidence).
- Never put tokens or keys in the repo: they are in the Windows Credential Manager (`CloudflarePages@<profile>`).
- Build and check before deploying: `web.py build <slug>`. Production only with `--prod --yes` after the user approved the preview URL.
