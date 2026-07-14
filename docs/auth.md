# Authentication

PharmaAssist uses **JWT Bearer** tokens and role-based access control.

## Roles

| Role | Read inventory | Add / update / delete | Sell | OCR / search | Register users / audit |
|------|----------------|-----------------------|------|--------------|-------------------------|
| `cashier` | Yes | No | Yes | Yes | No |
| `pharmacist` | Yes | Yes | Yes | Yes | No |
| `admin` | Yes | Yes | Yes | Yes | Yes |

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| POST | `/auth/login` | Public |
| GET | `/auth/me` | Any staff |
| POST | `/auth/register` | Admin |
| GET | `/auth/audit` | Admin |

Inventory, search, and OCR routes require a valid Bearer token.

## Local setup

1. Set in `.env`:

```env
JWT_SECRET=change-me-to-a-long-random-string
BOOTSTRAP_ADMIN_EMAIL=admin@example.com
BOOTSTRAP_ADMIN_PASSWORD=choose-a-strong-password
```

2. Start the API. On first boot with an empty `users` table, the bootstrap admin is created.
3. Login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@example.com\",\"password\":\"choose-a-strong-password\"}"
```

4. Call protected routes with `Authorization: Bearer <access_token>`.

## Audit

Successful **sell** and **delete** actions write rows to `audit_logs` (who, action, entity, JSON details). Admins list them via `GET /auth/audit`.

## Streamlit note

The current Streamlit UI does not yet send JWTs. After this change the API rejects unauthenticated inventory/OCR calls. Point the React/Streamlit client at `/auth/login` and attach the token, or use `/docs` to exercise the API while the UI catches up.
