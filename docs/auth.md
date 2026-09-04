# Authentication

PharmaAssist uses a **short-lived JWT access token** plus a **rotating refresh token**.
Primary UI: React `frontend-web`.

- **Access JWT** — sent as `Authorization: Bearer …` on staff routes. Held in **memory only** (never `localStorage`).
- **Refresh token** — opaque, stored hashed in the database, sent only as an **httpOnly** cookie (`pharmaassist_refresh`). JavaScript cannot read it.

System context: [architecture.md](architecture.md).

## Roles

| Role | Read inventory | Add / update / delete | Sell | OCR / search / agent | Reindex | Register users / audit |
|------|----------------|-----------------------|------|----------------------|---------|-------------------------|
| `cashier` | Yes | No | Yes | Yes | No | No |
| `pharmacist` | Yes | Yes | Yes | Yes | Yes | No |
| `admin` | Yes | Yes | Yes | Yes | Yes | Yes |

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| POST | `/auth/login` | Public. JSON: `{ access_token, expires_in, user }`. Sets refresh cookie. |
| POST | `/auth/refresh` | Refresh cookie. Rotates cookie; returns a new access JWT. |
| POST | `/auth/logout` | Refresh cookie. Revokes token and clears cookie. |
| GET | `/auth/me` | Access JWT |
| GET | `/auth/users` | Admin |
| POST | `/auth/register` | Admin |
| PATCH | `/auth/users/{id}` | Admin |
| GET | `/auth/audit` | Admin |

Inventory, sales, search, OCR, and agent routes require a valid Bearer access token.

## Local setup

1. Set in `.env`:

```env
JWT_SECRET=change-me-to-a-long-random-string
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=choose-a-strong-password
```

Optional: `JWT_EXPIRE_MINUTES` (default 15), `REFRESH_EXPIRE_DAYS` (default 7).

2. Start the API. On first boot with an empty `users` table, the bootstrap admin is created.
3. Login (use `-c` so curl stores the refresh cookie):

```bash
curl -c cookies.txt -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@example.com\",\"password\":\"choose-a-strong-password\"}"
```

4. Call protected routes with `Authorization: Bearer <access_token>`.
5. When the access token expires, `POST /auth/refresh` with the cookie (`curl -b cookies.txt`) returns a new JWT.

The React app sends `credentials: include`, keeps the access token in memory, and calls `/auth/refresh` on boot and on 401.

Cookie notes:

- Set in code as `HttpOnly`, `Secure`, `SameSite=None`, `Path=/auth` so a separate SPA origin (Vite, or Render static site + API) can send the cookie.
- Optional overrides: `COOKIE_SAMESITE` (`lax` / `strict` / `none`) and `COOKIE_SECURE`.

## Audit

Successful **sell**, **delete**, **staff register**, and **staff update** actions write rows to `audit_logs` (who, action, entity, JSON details). Admins list them via `GET /auth/audit` or the React **Admin** page (`/admin`).

Staff management rules:

- Admins cannot deactivate their own account.
- The last active admin cannot be demoted or deactivated.

## Streamlit note

The Streamlit UI does **not** send JWTs. Prefer the React app for auth-aware flows (`frontend-web`).
