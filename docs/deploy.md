# Deploying the web app (M6)

**Status:** the container file is written but **not built or run** here; this machine has no Docker. The first build happens on the host.

## Gates, in order

1. **PPQS permission (copyright gate, L4 §8).** The PPQS website policy allows reproduction free of charge **after permission by email**. Until it is granted, the link stays private (shared only with testers).
2. **A host account** (yours). **Not Hugging Face:** since its docs now say Docker Spaces need a paid plan to create (checked 2026-11-18), the free host is still to be chosen. Private tests need no host (see below).
3. **Secrets:** add `GROQ_API_KEY` (and optionally `GEMINI_API_KEY`) in the host's secret settings. They are never put in the image or the repository.

## Private tests now: from the laptop

The app runs here with `--behind-proxy`. A temporary tunnel gives testers a random HTTPS link. The keys stay in `~/.config/labelclaim/env` on this machine, so no host and no secrets settings are needed. The link works only while the laptop runs it. The per-minute bucket and the daily cap on `/v1/ask` still apply.

## Steps (a container host: kept for reference, written for Hugging Face before its Docker Spaces became paid)

1. Create a Space with the **Docker** SDK, set to **private**.
2. In the Space settings, add the secrets above.
3. Push this repository's files to the Space, **plus `build/register.sqlite`**: the release build, hash `285c851f…`. It is gitignored here, so add it to the Space only.
4. The Space builds the `Dockerfile` and serves on port 7860.
5. Check, in this order:
   - `/healthz` shows the build hash `285c851f…`;
   - Check works with `Emamectin benzoate 5% SG`, `bende`, `shoot and fruit borer` (approved, p. 25);
   - Ask answers in the picked language;
   - `/v1/ask` stops at the daily cap (800) with `daily_limit`.

## Known limits

- The per-client limit uses `X-Forwarded-For` (`--behind-proxy`). A client can forge that header, so the global daily cap on `/v1/ask` is what protects the model quota.
- A free Space sleeps when idle. The first request after a sleep is slow.
