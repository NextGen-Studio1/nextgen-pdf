# NextGen PDF — Full Integration Instructions

This package contains prepared frontend/search/performance fixes based on the supplied NextGen PDF source.

## First
1. Back up the current working project or commit it to git.
2. Extract this package next to the current project.
3. Use the master prompt supplied with this package in Antigravity.
4. Merge changes; do not overwrite newer API-unification work.

## Prepared in this package
- SEO metadata and canonicals across public HTML pages
- robots.txt and sitemap.xml regenerated from actual public pages
- Open Graph/Twitter metadata
- public tool structured data and breadcrumbs
- crawlable related-tool internal links
- visible tool supporting content
- missing js/theme.js implementation
- safer unversioned JS/CSS cache policy
- homepage privacy wording softened where it made an absolute unsupported claim
- scripts/seo_audit.py

## Still requires Antigravity/project verification
- unify all PDF tool endpoints under /api/v1 without duplicating converter logic
- verify all 48 tools end-to-end
- verify Word-to-PDF in the actual deployment image
- verify Firebase Auth and production credentials
- verify quota/rate limiting under concurrency
- verify dashboard ownership and downloads
- production security headers/CORS/docs exposure
- Business/API/payment functionality
- live browser/E2E deployment verification

Do not claim any of these are complete until tests prove them.
