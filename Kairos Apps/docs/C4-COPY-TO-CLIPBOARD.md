# C4 — Copy Kairos Day Report

## Purpose

Copy a completed `Kairos Day Report` from Frappe Desk so it can be pasted manually into Teams,
Notepad, email, or another destination. Kairos does not send data to Teams directly.

## Manual verification

1. Run `bench --site kairos.local migrate`, then restart `bench start` and hard-refresh Desk.
2. Open a saved **Kairos Day Report** with a non-empty **Summary**.
3. Open the **Copy** menu and choose **Summary**.
4. Paste into Notepad. The pasted text must equal `summary_text`.
5. Choose **Copy → Summary + Timeline**, then paste again. The summary must appear first, followed
   by `---` and `timeline_text`.

## Expected behavior

- If Summary is empty, Kairos asks the user to generate it first.
- A successful copy shows a green confirmation message.
- Kairos first uses the browser Clipboard API. On local HTTP Desk sites where that API is blocked,
  it falls back to the browser's legacy copy command.
- If both browser methods are rejected, Kairos shows an actionable permission message. No report
  content is sent to an external service during copy.
