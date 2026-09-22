# Deployment Integration

After Antigravity integration:

1. Run the local SEO audit.
2. Run backend tests and tool smoke tests.
3. Confirm Firebase Hosting serves clean public URLs and the custom 404.
4. Confirm the Render backend URL is healthy and CORS permits only intended frontend origins.
5. Deploy frontend.
6. Deploy backend only after local integration tests pass.
7. In Google Search Console, verify the property and submit `/sitemap.xml`.
8. In Bing Webmaster Tools, verify the site and submit the same sitemap.
9. Use Search Console/Bing query data to decide which tool pages need additional content later.

Do not assume ranking is immediate; indexing and ranking are search-engine processes outside the codebase.
