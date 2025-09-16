Password reset links
---------------------

The password reset email uses a configurable frontend base URL to build the link users click.

Environment variable:

- `FRONTEND_BASE_URL` – e.g. `https://portal.example.com` or `http://localhost:5173`

If not set, it defaults to `http://localhost:5173`.

Example (Windows PowerShell):

```powershell
$env:FRONTEND_BASE_URL = "https://your-domain.com"
```

Then restart the backend so the change takes effect.

