# Serving the portfolio at portfolio.creativedatasolutions.tech (optional)

By default the site lives at `https://<username>.github.io/cds-portfolio/`.
To use a subdomain of your own domain instead:

1. Wherever your DNS for creativedatasolutions.tech is managed (WordPress.com,
   since the domain was transferred there), add a **CNAME** record:
   name `portfolio`, value `<username>.github.io`.
2. On GitHub: repository → **Settings → Secrets and variables → Actions →
   Variables tab → New repository variable**. Name `CUSTOM_DOMAIN`, value
   `portfolio.creativedatasolutions.tech`. (This makes the workflow skip the
   `/cds-portfolio` base path and write a CNAME file into the build.)
3. **Settings → Pages → Custom domain**: enter the same hostname, save, and
   tick **Enforce HTTPS** once the certificate is issued (can take up to an hour).
4. Re-run the `pipeline` workflow from the Actions tab.

Then link `https://portfolio.creativedatasolutions.tech` from the WordPress
nav. Until this is done, link the github.io URL; either works.
