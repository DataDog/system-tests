/// Sensitive query parameter key patterns (case-insensitive substrings).
const SENSITIVE_KEYS: &[&str] = &[
    "pass",
    "password",
    "secret",
    "api_key",
    "apikey",
    "auth",
    "credentials",
    "mysql_pwd",
    "private_key",
    "public_key",
    "token",
    "application_key",
    "access_token",
    "client_secret",
];

fn is_sensitive_key(key: &str) -> bool {
    let lower = key.to_lowercase();
    SENSITIVE_KEYS.iter().any(|&s| lower.contains(s))
}

pub fn scrub_query_string(query: &str) -> String {
    let mut parts = Vec::new();
    for pair in query.split('&') {
        if let Some(eq_pos) = pair.find('=') {
            let key = &pair[..eq_pos];
            if is_sensitive_key(key) {
                // Replace the entire key=value pair with <redacted>
                parts.push("<redacted>".to_owned());
            } else {
                parts.push(pair.to_owned());
            }
        } else {
            parts.push(pair.to_owned());
        }
    }
    parts.join("&")
}
