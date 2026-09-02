# Exercise 4: Add the Weblog Endpoint

## Background

`test_new_endpoint` fails because `/my_training4_endpoint` doesn't exist yet. The Java Spring Boot weblog's main controller lives at:

```
utils/build/docker/java/spring-boot/src/main/java/com/datadoghq/system_tests/springboot/App.java
```

> **Important rule:** every new weblog endpoint **must** be documented in the "Endpoints" section of `docs/understand/weblogs/end-to-end_weblog.md`.

After changing weblog source, you must **rebuild** the image — the running container still has the old app until you do.

## Goal

Add **`GET /my_training4_endpoint`** to the Java Spring Boot weblog. It must return the plain text body `Training4!` with HTTP status `200`, so `test_new_endpoint` passes.

## Hints

1. Follow the same pattern as other simple `@GetMapping` endpoints already in `App.java` (e.g. `home()` on `/`, or `/waf`).
2. Returning a `String` from a `@GetMapping` method gives a `200` with that string as the body — nothing extra needed.
3. Don't touch any existing endpoint or import.
4. Rebuild with the **language + weblog** form: `./build.sh java -w spring-boot`.

## Expected Result

```java
@GetMapping("/my_training4_endpoint")
String myTraining4Endpoint() {
    return "Training4!";
}
```

And a matching entry in `docs/understand/weblogs/end-to-end_weblog.md`:

````markdown
### GET /my_training4_endpoint

The following text must be written to the body of the response:

```
Training4!
```
````

## Verification

```bash
./build.sh java -w spring-boot
./run.sh tests/test_training4.py
```

Now answer the following questions:

- Does `test_new_endpoint` pass now?
- Do `test_root_ok` and `test_root_wrong` still behave exactly as before?
- What would happen if you forgot to rebuild the weblog before re-running the tests?

## Bonus / Follow-up Questions

1. `spring-boot`, `spring-boot-jetty`, `spring-boot-undertow`, ... all share `App.java`. Why do they get the endpoint "for free"?
2. Why must a shared endpoint be implemented in every relevant weblog, not just one, before a shared test can rely on it in CI?
3. Which manifest marker would you use to scope `test_new_endpoint` so it only runs where the endpoint exists (Java `spring-boot*` weblogs), and how would you scope Java itself to exclude the non-Spring-Boot variants (`akka-http`, `vertx3`, ...)?
