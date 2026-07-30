# app.html — patched, ready to commit

19 changes across 105 lines. Verified: JS parses clean, 16/16 DOM tests pass
against live XSS payloads.

## What changed

| # | Change | Why |
|---|---|---|
| 1 | Added `H()` HTML-escape helper | Used by every fix below |
| 2 | Escaped 11 `innerHTML` render paths | Patient/visit fields could inject JS |
| 3 | Fixed 5 broken `onclick` handlers | See "the bug the audit missed" below |
| 4 | Visits read now uses `visits_safe` | Server-side financial masking |
| 5 | Removed `PIN_CODE='2088'` | Was visible in page source |
| 6 | Doctor mode now checks `AUTH.role` | Replaces the PIN gate |
| 7 | Emptied `DEFAULT_T` / `DEFAULT_C` | Staff names + procedure list were public |
| 8 | Role refreshes on every app start | Self-heals stale sessions |

## The bug the audit missed

Five `onclick` handlers used `.replace(/'/g,"\'")` to escape apostrophes.
In a double-quoted JS string `\'` is just `'` — **the replace was a no-op.**
Two consequences:

- A patient named `O'Brien` silently broke their row's buttons
- A crafted name injected JS straight into the handler

Fixed by moving values into `data-` attributes and reading them via
`this.dataset`, so no user text ever lands inside a JS string literal.

## Writes are untouched

Only the read moved to the view. Verified by grep:

```
line 595  visits_safe?select=...     READ
line 799  visits  POST               write
line 828  visits?id=eq. PATCH        write
line 835  visits?id=eq. DELETE       write
line 916  visits?patient_name= PATCH write
```

## To deploy

```bash
cp ~/Downloads/app.html .
git add app.html
git commit -m "Security: escape output, server-side role gate, remove hardcoded PIN"
git push
```

## Test after deploying

1. Hard refresh (Cmd/Ctrl+Shift+R)
2. Log in as owner — all 957 patients and 2,062 visits load
3. Financial columns show real numbers
4. Triple-tap the logo — doctor mode unlocks with **no PIN prompt**
5. Add a visit, edit a visit, edit a patient — all save
6. Treatment + consultant dropdowns still populate
7. Create a patient named `<b>TEST</b>` — must display with visible angle
   brackets, not bold. Then delete it.
8. Log in as Gold Dental Studio — sees only their own data

Rollback if needed: `git revert HEAD && git push`

## Two things to know

**Dropdowns now depend entirely on the SETTINGS row.** The hardcoded fallback
is gone. All three clinics have their SETTINGS row (verified: ids 3718, 3785,
3788), so this is safe — but if that row is ever deleted, the dropdowns go
empty rather than falling back.

**Nothing is actually restricted yet.** All three accounts are `role='owner'`,
so `visits_safe` still returns full financial data to everyone — same as
before. The masking only takes effect once an assistant account exists:

```sql
-- after creating the user in Supabase Dashboard > Authentication > Users
insert into clinic_members (user_id, clinic_id, role)
values ('NEW-USER-UID', '00000000-0000-0000-0000-000000000001', 'assistant');
```

Then log in as that account and confirm fee columns show `—`.

## Still outstanding

- **All data still loads into browser memory.** Needs server-side pagination —
  a real rewrite, not a patch. `visits_safe` does reduce exposure: assistants
  never receive financial fields at all.
- **Session token in localStorage.** Switching to `sessionStorage` means
  re-login on every tab close. Genuine trade-off, left as-is.
- **Base table still readable.** After the assistant account is confirmed
  working, the last step is `revoke select on public.visits from authenticated;`
  — do not run this before then or the app breaks.
- **Dead PIN markup remains** in the HTML (overlay div, keypad). Harmless —
  `showPIN()` is a no-op stub so it can never display. Left in place rather
  than risk breaking layout.
