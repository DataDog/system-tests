use axum::http::HeaderMap;

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

pub fn extract_hostname_from_referer(referer: &str) -> Option<String> {
    if referer.is_empty() {
        return None;
    }
    // Only http/https schemes
    let rest = referer
        .strip_prefix("https://")
        .or_else(|| referer.strip_prefix("http://"))?;

    // Strip userinfo if present (user:pass@)
    let rest = if let Some(at_pos) = rest.find('@') {
        &rest[at_pos + 1..]
    } else {
        rest
    };

    // Hostname ends at '/', '?', '#', or ':' (port)
    let end = rest
        .find(|c| c == '/' || c == '?' || c == '#' || c == ':')
        .unwrap_or(rest.len());
    let hostname = &rest[..end];
    if hostname.is_empty() {
        None
    } else {
        Some(hostname.to_owned())
    }
}

// ─── Client IP extraction ────────────────────────────────────────────────────

/// Extract the best client IP from the request headers.
/// Follows Datadog's priority order for IP headers.
pub fn extract_client_ip(headers: &HeaderMap) -> Option<String> {
    // Headers in priority order (single-value headers first, then multi-value)
    let priority_headers = [
        "x-client-ip",
        "x-real-ip",
        "true-client-ip",
        "fastly-client-ip",
        "cf-connecting-ip",
        "cf-connecting-ipv6",
        "x-forwarded-for",
        "forwarded-for",
        "x-cluster-client-ip",
    ];

    for header_name in &priority_headers {
        if let Some(value) = headers.get(*header_name) {
            if let Ok(value_str) = value.to_str() {
                // For comma-separated lists, find the first public IP
                for candidate in value_str.split(',') {
                    let ip = candidate.trim().to_owned();
                    if !ip.is_empty() && is_public_ip(&ip) {
                        return Some(ip);
                    }
                }
                // If no public IP found, return first non-empty
                if let Some(first) = value_str.split(',').next() {
                    let ip = first.trim().to_owned();
                    if !ip.is_empty() {
                        return Some(ip);
                    }
                }
            }
        }
    }
    None
}

/// Returns true if the IP is a publicly routable IP address.
fn is_public_ip(ip: &str) -> bool {
    use std::net::IpAddr;
    let Ok(addr) = ip.parse::<IpAddr>() else {
        return false;
    };
    match addr {
        IpAddr::V4(v4) => {
            !v4.is_private()
                && !v4.is_loopback()
                && !v4.is_link_local()
                && !v4.is_broadcast()
                && !v4.is_multicast()
                && !v4.is_unspecified()
        }
        IpAddr::V6(v6) => {
            !v6.is_loopback()
                && !v6.is_multicast()
                && !v6.is_unspecified()
                // filter link-local (fe80::/10)
                && (v6.segments()[0] & 0xffc0) != 0xfe80
                // filter unique-local (fc00::/7)
                && (v6.segments()[0] & 0xfe00) != 0xfc00
        }
    }
}
