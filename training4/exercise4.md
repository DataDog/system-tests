# Exercise 4: Add the Weblog Endpoint

## Background

`test_new_endpoint` fails because `/my_labs_endpoint` doesn't exist yet. The Node.js Express weblog's main app lives at:

```
utils/build/docker/nodejs/express/app.js
```

> **Important rule:** every new weblog endpoint **must** be documented in the "Endpoints" section of `docs/understand/weblogs/end-to-end_weblog.md`.

After changing weblog source, you must **rebuild** the image — the running container still has the old app until you do.

## Goal

Add **`GET /my_labs_endpoint`** to the Node.js Express weblog. It must return the plain text body `Labs!` with HTTP status `200`, so `test_new_endpoint` passes.

## Hints

1. Follow the same pattern as other simple `app.get(...)` routes already in `app.js` (e.g. the handler for `/`).
2. Set `Content-Type` to `text/plain` and call `res.send(...)` with the body — Express defaults to `200` when you don't set a status explicitly.
3. Don't touch any existing endpoint or import.
4. Rebuild with the **language + weblog** form: `./build.sh nodejs -w express4`.

## Expected Result

```javascript
app.get('/my_labs_endpoint', (req, res) => {
  res.set('Content-Type', 'text/plain')
  res.send('Labs!')
})
```

And a matching entry in `docs/understand/weblogs/end-to-end_weblog.md`:

````markdown
### GET /my_labs_endpoint

The following text must be written to the body of the response:

```
Labs!
```
````

## Verification

```bash
./build.sh nodejs -w express4
./run.sh tests/test_labs.py
```

Now answer the following questions:

- Does `test_new_endpoint` pass now?
- Do `test_root_ok` and `test_root_wrong` still behave exactly as before?
- What would happen if you forgot to rebuild the weblog before re-running the tests?

## Bonus / Follow-up Questions

1. `express4`, `express5`, `express4-typescript`, `uds-express4`, ... all share `app.js`. Why do they get the endpoint "for free"?
2. Why must a shared endpoint be implemented in every relevant weblog, not just one, before a shared test can rely on it in CI?
3. Which manifest marker would you use to scope `test_new_endpoint` so it only runs where the endpoint exists (Node.js `express*` weblogs), and how would you scope Node.js itself to exclude the non-Express variants (`fastify`, `nextjs`, ...)?
