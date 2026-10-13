# Source acquisition decisions — October 12, 2026

- The user asked this chat to obtain the source content and stated they do not
  have the source code. We used the named-URLs-only scope presented in their
  question: the 14 public source URLs explicitly listed in the attached brief.
- All three robots.txt files were retrieved and contain `User-agent: *` and
  `Disallow: /`. The web browsing tool could not retrieve these files; direct
  HTTP retrieval returned 200. Robots records are preserved in receipts/.
- No maintainer authorization for a robots-disallowed recursive crawl was
  asserted or recorded. The roughly 500-page crawler was not run. If the
  implementation brief requires robots compliance for all acquisition, these
  one-time direct snapshots should be recorded as the named-URL scope decision,
  not described as a robots-compliant crawl.
- Requests used an identifying user agent, no credentials, no form submissions,
  no retries or redirect following, and at least 1.1 seconds between request
  starts to the same host. The only live requests made by the download script
  were the 14 named source URLs plus three robots.txt requests.
- Linked content, scripts, stylesheets and images were inventoried from local
  HTML without requesting them. The archive is for offline implementation.
- Public HTML does not expose original classic-ASP source, server configuration,
  databases, or all underlying product logic. Those require a maintainer export.
