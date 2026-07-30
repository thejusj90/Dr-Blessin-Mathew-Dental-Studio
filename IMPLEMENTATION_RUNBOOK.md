# Implementation Runbook — app.html Security Fixes

Work through this top to bottom. Don't skip ahead — Step 6 breaks the app if
Step 5 isn't done, and Step 7 breaks it if Step 4 isn't done.

Each step ends with a test and a commit. Commit after each working step, not
once at the end — if something breaks three steps later you want a clean point
to return to.

---

## STEP 0 — Set up a safe working state

```bash
cd /path/to/Dr-Blessin-Mathew-Dental-Studio
git status                    # confirm clean, nothing uncommitted
git checkout -b security-fixes
cp app.html app.html.backup   # local safety copy, do not commit this
```

Add the backup to gitignore so it never gets pushed:

```bash
echo "app.html.backup" >> .gitignore
```

**Rollback at any point:**
```bash
git checkout app.html         # undo uncommitted changes
git reset --hard HEAD~1       # undo the last commit
```

---

## STEP 1 — Confirm the audit's code actually matches your file

Before changing anything, verify these exist. If a search returns nothing,
that fix doesn't apply to your file and you should skip it rather than guess.

```bash
grep -n "PIN_CODE" app.html
grep -n "DEFAULT_C" app.html
grep -n "DEFAULT_T" app.html
grep -n "localStorage" app.html
grep -n "from('visits')" app.html
grep -n 'from("visits")' app.html
grep -n "innerHTML" app.html
```

Write down the line numbers you get. The audit's numbers may be stale.

**Note the count from that last command** — that's how many places need XSS
review in Step 2.

---

## STEP 2 — XSS sanitisation (highest priority)

### 2.1 Add the helper

Open `app.html`. Find the constant block near the top of the main `<script>`
(where `SB_URL` and `SB_KEY` are declared). Add immediately after it:

```javascript
function esc(s){
  if(s===null||s===undefined) return '';
  const d=document.createElement('div');
  d.textContent=String(s);
  return d.innerHTML;
}
```

### 2.2 Wrap the three confirmed spots

| Find | Replace with |
|---|---|
| `${p.name}` | `${esc(p.name)}` |
| `${v.patient_name\|\|''}` | `${esc(v.patient_name)}` |
| `${v.diagnosis\|\|'` | `${esc(v.diagnosis)\|\|'` |

### 2.3 Sweep the rest

Go through every line from `grep -n "innerHTML" app.html`. In each template
literal, wrap any `${...}` containing one of these fields:

```
name  patient_name  phone  age  gender  diagnosis
treatment  consultant  remarks  pid
```

Leave numeric and date fields alone: `id`, `cons_fee`, `clinic_share`,
`lab_cost`, `visit_date`, `created_at`.

### 2.4 Test

1. Open the app, log in as the Blessin owner account
2. Add a test patient with the name: `<b>XSSTEST</b>`
3. **The name must display with visible angle brackets as literal text.** If it
   renders as bold "XSSTEST", that view still isn't escaped — find it and fix it
4. Check the patient appears correctly in: patient list, search suggestions,
   visit table, and any printed/exported view
5. Delete the test patient

### 2.5 Commit

```bash
git add app.html .gitignore
git commit -m "Escape user-supplied values before innerHTML insertion"
```

---

## STEP 3 — Remove hardcoded staff and treatment lists

Both already load from the `SETTINGS` row in `patients` (verified present for
all three clinics: ids 3718, 3785, 3788). The arrays are only fallbacks.

### 3.1 Replace

Find the two declarations and empty them:

```javascript
const DEFAULT_T=[];
const DEFAULT_C=[];
```

### 3.2 Test — this one has real regression risk

1. Reload the app fully (hard refresh: Ctrl+Shift+R / Cmd+Shift+R)
2. Open the treatment dropdown — must still populate
3. Open the consultant dropdown — must still populate
4. **Log in as the Gold Dental Studio account and check both dropdowns again**
   — different clinic, different SETTINGS row
5. If either is empty, the SETTINGS load isn't working and you must revert:
   `git checkout app.html`

### 3.3 Commit

```bash
git commit -am "Load treatment and consultant lists from SETTINGS only"
```

---

## STEP 4 — Switch visit reads to visits_safe

The view is already live in your Supabase project and verified working.

### 4.1 Change only the read query

Find the visits `.select()` chain (likely in `loadData()`):

```javascript
.from('visits')      →      .from('visits_safe')
```

**Only the read.** Any `.from('visits')` followed by `.insert()`,
`.update()`, `.upsert()` or `.delete()` must stay as `visits` — you cannot
write through the view.

Verify you changed the right ones:
```bash
grep -n "visits_safe" app.html      # should be your select only
grep -n "from('visits')" app.html   # should be your writes only
```

### 4.2 Null-guard the financial fields

For non-owner accounts these arrive as `null`. Find every use:

```bash
grep -n "cons_fee\|clinic_share\|lab_cost" app.html
```

Anywhere they're summed or formatted, add a fallback:

```javascript
(v.cons_fee||0)  (v.clinic_share||0)  (v.lab_cost||0)
```

### 4.3 Test

1. Log in as the Blessin owner
2. Visit list loads, all 2,062 rows present
3. Financial columns show real numbers (owner role — nothing should be hidden yet)
4. Daily/monthly totals still calculate correctly
5. **Add a new visit** — must still save (this confirms writes still go to `visits`)
6. **Edit an existing visit** — must still save
7. Log in as Gold Dental Studio — sees only their own visits

### 4.4 Commit

```bash
git commit -am "Read visits through visits_safe view"
```

---

## STEP 5 — Create a real assistant account

**Everything above is cosmetic until this step.** All three of your accounts
are currently `role = 'owner'`, so `visits_safe` returns full financial data
to everyone. This is what makes the restriction real.

### 5.1 Create the user

Supabase Dashboard → Authentication → Users → **Add user**
- Email: the assistant's own email address
- Set a password, or send an invite
- Copy the generated **User UID**

### 5.2 Assign the assistant role

Dashboard → SQL Editor, paste and run (substituting the UID):

```sql
insert into clinic_members (user_id, clinic_id, role)
values (
  'PASTE-USER-UID-HERE',
  '00000000-0000-0000-0000-000000000001',
  'assistant'
);
```

That clinic_id is Dr. Blessin's Dental Studio.

### 5.3 Verify

```sql
select cm.user_id, cm.role, c.name
from clinic_members cm join clinics c on c.id = cm.clinic_id;
```

You should now see one `assistant` alongside the three `owner` rows.

### 5.4 Test the actual restriction

1. Log in as the **new assistant account** (use a private/incognito window so
   you don't lose your owner session)
2. Patient list and visit list load normally
3. **Financial columns are blank or zero** — this is the fix working
4. Open browser console and type `visits` (or whatever the variable is) —
   `cons_fee`, `clinic_share`, `lab_cost` should all be `null`
5. Log back in as owner — financial data returns

If step 3 still shows real numbers, the frontend is still reading `visits`
somewhere. Go back to Step 4.1.

---

## STEP 6 — Remove the hardcoded PIN

**Only after Step 5 passes.** Removing the PIN first leaves no mode
separation at all.

### 6.1 Delete the constant

```javascript
const PIN_CODE='2088';        // delete this line
```

### 6.2 Replace with a role check

Where the app currently determines doctor mode, use the role from the
membership lookup you already do at login:

```javascript
const { data: member } = await sb
  .from('clinic_members')
  .select('clinic_id, role')
  .eq('user_id', session.user.id)
  .single();

const isDoctor = member && ['owner','doctor'].includes(member.role);
```

Use `isDoctor` wherever the PIN previously set the mode. Remove the PIN entry
screen and `pinPress()` handler.

### 6.3 Test

1. Owner login → sees financial data, no PIN prompt
2. Assistant login → no financial data, no PIN prompt
3. Console: `setDoctorMode(true)` or `isDoctor=true` as the assistant → the UI
   may change, but **financial values stay null**. That's the point: the
   bypass is now harmless because the data never reached the browser

### 6.4 Commit

```bash
git commit -am "Replace client-side PIN with server-side role check"
```

---

## STEP 7 — Lock the base table (final step)

**Only after Steps 4-6 all pass in production.** This closes the last hole:
without it, anyone can query `visits` directly from the console and get the
financial fields regardless of the view.

Tell me when you've reached this point and I'll run it against your project,
or run it yourself in the SQL Editor:

```sql
revoke select on public.visits from authenticated;
grant select on public.visits_safe to authenticated;
```

**Test immediately after:** reload the app as owner, confirm visits still load.
If they don't, roll back instantly:

```sql
grant select on public.visits to authenticated;
```

---

## STEP 8 — Merge and deploy

```bash
git checkout main
git merge security-fixes
git push origin main
```

Then verify the live site: hard refresh, log in as owner, log in as assistant,
confirm both behave as tested locally.

---

## STEP 9 — Session storage (optional, genuine trade-off)

Switching `localStorage` → `sessionStorage` means staff re-login every time
they close the tab. Good on a shared front-desk machine, annoying on personal
devices. Your call.

If you do it, change **all three**:
```bash
grep -n "localStorage" app.html
```
`setItem`, `getItem`, and `removeItem` must all switch together, or login breaks.

---

## Not covered here

- **All data still loads into browser memory.** Fixing it means server-side
  pagination and search — a real rewrite of `loadData()`, not a patch. The
  `visits_safe` change does reduce the exposure: financial fields are no longer
  in memory for assistants at all.
- **Login rate limiting.** Set this in Supabase Dashboard → Authentication →
  Rate Limits, not in code.
- **Security headers.** Depends where you're hosting — tell me the host and
  I'll give you the right approach. GitHub Pages can't set headers at all; a
  CSP meta tag is the only option there, and it needs careful testing.

---

## If something breaks

1. `git checkout app.html` — undo uncommitted edits
2. `git reset --hard HEAD~1` — undo the last commit
3. For Step 7: `grant select on public.visits to authenticated;`
4. Nothing in Steps 1-6 touches the database schema, so your data is never at
   risk — only the frontend behaviour changes
