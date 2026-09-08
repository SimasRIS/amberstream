# AmberStream — Security Training Lab

> ⚠️ **This is a deliberately vulnerable build.** Run it on **localhost inside an
> isolated VM only.** Never expose it to a network, never point it at real data,
> and never deploy it. The vulnerability below is real.

The application contains a **stored cross-site-scripting (XSS)** hole in the
customer reviews feature. It is always active — there is no difficulty switch
and no on-page warning; this is a fixed vulnerable target.

## Running

```bash
python3 app.py            # http://localhost:5000
```

## The vulnerability

Anyone can submit a review at **`/reviews.html`**. The review body is stored and
later displayed — on the public reviews page, on the homepage, and in the staff
moderation queue — as **raw HTML**, after a weak blocklist filter.

The filter (`review_html` in `app.py`) removes, case-insensitively:

- `<script>` tags
- `javascript:` URIs
- the event handlers `onerror`, `onload`, `onclick`, `onmouseover`

It is a **blocklist**, so it is incomplete: it forgets every other event
handler.

### Intended bypass

```html
<input autofocus onfocus=alert(document.cookie)>
```

`autofocus` fires `onfocus` with no user interaction, and `onfocus` is not on
the blocklist — so the JavaScript runs.

### Where it fires

1. Submit the payload as a review body on `/reviews.html`.
2. It executes when a moderator opens **`/admin/reviews`** (the queue renders the
   body the same way, so a *pending* review can attack the admin), or once the
   review is approved and shown publicly.

### Impact

- Session / cookie theft from visitors and from signed-in staff.
- Takeover of the staff console via a moderator's session.
- Defacement or redirection of the customer-facing pages.

> The automated checks confirm the payload reaches the page un-escaped (the
> precondition for execution). Confirm the actual pop-up in a browser inside the
> VM.

## The fix

Escape on **output**, do not blocklist the **input**. Rendering the body through
the template engine's auto-escaping — `{{ review.body }}` with no `| safe` and
no filter — turns the markup into inert text and closes the hole. Blocklists are
always incomplete, which is exactly what this exercise demonstrates.

## Where the code lives

- `app.py` — the `review_html` template filter (the vulnerable blocklist).
- `templates/_macros.html`, `templates/admin/reviews.html` — the render sites.

## Other weaknesses in this build

Separate from the XSS, and also reasons never to expose this app:

- Passwords are stored in plaintext and compared with `==`.
- The Flask `SECRET_KEY` falls back to a hardcoded development value.
- Default staff credentials are `admin` / `admin`.
- No CSRF protection on any form.
- Review moderation actions have no ownership checks (IDOR by design).
