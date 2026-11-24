# Security audit

24 November 2026. Review addressed public read-only application routes,
the optional provider integration, and the local deployment configuration.

| Area | Control and evidence |
|---|---|
| Input | Bounds for query bytes, route IDs, page sizes and pagination. SQL uses bound parameters. Added regression for HTTP 414. |
| Concurrency | The journey API caps concurrent queries per worker. Excess requests return 429 and `Retry-After`. |
| Errors and logs | Generated request IDs correlate server logs and response headers. Request logs use method, route template, status and duration. API server errors return generic messages. Docker disables Uvicorn access logs. |
| Live feed | Optional server-only secret, fixed HTTPS provider endpoint, redirect rejection, bounded body and read time, freshness checks and no browser access to the key. HTTP client logging suppresses URL-level INFO and DEBUG output. |
| Origins | CORS allows configured exact origins. Same-origin Caddy needs no CORS openings. |
| Proxy | Caddy has connection and upstream header timeouts, MIME sniffing and framing controls, plus default same-origin routing. |
| Container | Backend runs as UID 10001. Feed mount is read-only. Runtime requirements exclude pytest and use a tested dependency constraints file. |
| Dependencies | `npm audit --omit=dev` reported zero advisories. `pip check` found no broken requirements. The initial Python scan flagged pytest 8.4.2 (PYSEC-2026-1845). After moving to pytest 9.2.0, pip-audit found zero advisories across 35 checked pins. |

The app exposes schedule and historical aggregate endpoints. Keep the database
and raw ETM files outside source control and out of public static mounts.
Exception diagnostics from the server or infrastructure may still contain
internal details. Restrict access to logs and secret stores. The concurrency
control is process-local and public deployment still requires host-level
monitoring and a traffic policy suited to the expected load.
[Deployment controls](DEPLOYMENT_GUIDE.md)

## Journey update verification

The revised journey query keeps stop IDs bound and adds a fixed set of
accepted search modes. Date-related errors describe the Delhi search policy.
Historical demand failures return public reason codes without exposing local
artifact paths. Release verification reran the npm production and pinned
Python advisory checks. Both checks found zero known vulnerabilities at
verification time. The 24 November hosted CORS probe confirmed that the
public stops endpoint allowed the Vercel origin. The Windows workspace and
private hosting settings are outside the scope of that probe.
[Hosted smoke checks](FINAL_TEST_REPORT.md#hosted-smoke-checks)
