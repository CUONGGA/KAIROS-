# A7 — Collector authentication

Run migration after updating the Kairos app. It creates the `Kairos Collector` role and grants it only **Read**, **Create**, and **Write** access to `Kairos Event`; it has no Desk access and cannot delete events.

```bash
bench --site kairos.local migrate
```

In Desk, create a dedicated enabled user such as `kairos-collector@example.invalid`, assign the **Kairos Collector** role, then use the user's **API Access** section to generate an API key and secret. Keep the secret only in the developer machine's environment:

```bash
export KAIROS_FRAPPE_URL="http://kairos.local:8001"
export KAIROS_FRAPPE_TOKEN="<api_key>:<api_secret>"
```

The collector sends this value as the Frappe token header:

```text
Authorization: token <api_key>:<api_secret>
```

Verify that the token can create an event using the A6 curl request. Revoke and regenerate the user token if it is exposed; never commit either value.
