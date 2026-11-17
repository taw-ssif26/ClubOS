#!/usr/bin/env bash
# Post-deploy smoke test.  Usage: scripts/verify-deploy.sh https://yourdomain.com
set -u
B="${1:?usage: verify-deploy.sh https://yourdomain.com}"; B="${B%/}"; fail=0
ok()  { printf "  PASS  %s\n" "$1"; }
bad() { printf "  FAIL  %s\n" "$1"; fail=1; }
chk() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

echo "== reachability"
chk "site responds 200"                    '[ "$(curl -s -o /dev/null -w %{http_code} "$B/")" = 200 ]'
chk "API health through the proxy"         'curl -s "$B/api/health" | grep -q "\"ok\":true"'
chk "pricing renders DB content (৳)"       'curl -s "$B/pricing" | grep -q "৳"'
chk "terms and privacy pages exist"        '[ "$(curl -s -o /dev/null -w %{http_code} "$B/terms")$(curl -s -o /dev/null -w %{http_code} "$B/privacy")" = 200200 ]'

echo "== client-IP trust (rate limits and login history depend on this)"
spoof=$(curl -s -H 'X-Forwarded-For: 1.2.3.4' -H 'X-Real-IP: 5.6.7.8' "$B/api/whoami")
chk "spoofed X-Forwarded-For is NOT trusted (got: $spoof)" '! echo "$spoof" | grep -qE "1\.2\.3\.4|5\.6\.7\.8"'

echo "== transport + headers"
case "$B" in https://*) chk "HTTP redirects to HTTPS" '[ "$(curl -s -o /dev/null -w %{http_code} "http://${B#https://}/")" -ge 300 ]'
  chk "HSTS present" 'curl -sI "$B/" | grep -qi strict-transport-security';; *) echo "  skip  HTTPS checks (not an https URL)";; esac
chk "clickjacking protection (X-Frame-Options)" 'curl -sI "$B/" | grep -qi "x-frame-options: DENY"'
chk "nosniff"                               'curl -sI "$B/" | grep -qi "x-content-type-options: nosniff"'
chk "CSP present"                           'curl -sI "$B/" | grep -qi content-security-policy'

echo "== API not directly exposed / protected endpoints"
chk "admin API rejects anonymous (401)"     '[ "$(curl -s -o /dev/null -w %{http_code} "$B/api/admin/stats")" = 401 ]'
case "$B" in https://*) chk "API docs/schema are not exposed in production" '[ "$(curl -s -o /dev/null -w %{http_code} "$B/api/openapi.json")" != 200 ]';; esac
chk "login sets HttpOnly cookie, no token in body" 'r=$(curl -s -D - -o /tmp/vd.body -X POST "$B/api/auth/login" -H "Content-Type: application/json" -d "{\"email\":\"nobody@invalid.test\",\"password\":\"x\"}"); ! grep -q "\"token\"" /tmp/vd.body'
echo; [ $fail = 0 ] && echo "ALL CHECKS PASSED" || { echo "SOME CHECKS FAILED"; exit 1; }
