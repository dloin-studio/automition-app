# Involeap desktop app

## Get Involeap.exe (pick ONE; I could only build/test on Linux, so the Windows .exe must be built on Windows)

**A. GitHub (no install on your PC, free)**
1. Create a free GitHub repo, upload ALL files from this folder (keep the `.github/workflows` folder).
2. Repo -> Actions tab -> "Build Involeap.exe" -> Run workflow (~3 min).
3. Open the finished run -> Artifacts -> download `Involeap-windows` -> unzip -> `Involeap.exe`.

**B. On your own Windows PC**
1. Install Python 3.10+ from python.org (tick "Add python.exe to PATH").
2. Double-click `build.bat`. Result: `dist\Involeap.exe`.

Windows SmartScreen may warn about an unsigned app: "More info" -> "Run anyway" (code-signing costs money).

## Using the app
1. Put `Involeap.exe` in its own folder (it creates `inbox`, `out`, `involeap.db`, `.env` next to itself - back that folder up).
2. **Settings** tab: paste your free Gemini key (aistudio.google.com) -> Save -> "Test Gemini key".
3. Every day: export each WhatsApp group (Chat -> More -> Export chat -> Include media) -> **Run** tab -> "Add export files" -> **Run**.
4. **Review** tab: check each draft next to the original messages and poster, fix fields, Approve or Reject. Export approved items as JSON.
5. Optional dashboard sync: fill in the Supabase settings (run `schema.sql` there once).

Try it without a key first: tick "Test mode".

Command line still works: `python involeap.py --mock --no-push`
