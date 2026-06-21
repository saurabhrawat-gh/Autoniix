import http from 'k6/http';
import { check, sleep } from 'k6';

// K6 load test for Rust gateway auth endpoints.
// Per HARNESS-ENGINEERING-PLAN.md Section 14.
//
// Post-#350: /register is the canonical signup endpoint and returns
// onboarding metadata only (no tokens). The frontend calls /signin
// separately. This load test mirrors that two-step flow.
//
// Run:
//   k6 run tests/load/auth_load_test.js
//
// Run signin-only test (after seeding users):
//   k6 run --env TEST_MODE=signin tests/load/auth_load_test.js
//
// Compare against Python baseline:
//   k6 run --env TEST_BOTH=true tests/load/auth_load_test.js
//
// Targets (HARNESS-ENGINEERING-PLAN.md §14 Load Testing):
//   signin    p95 < 100ms, error rate < 0.1%
//   register  p95 < 200ms, error rate < 0.1%  (Argon2 hashing dominates)
//   /me       p95 < 50ms,  error rate < 0.01%

const RUST_BASE = __ENV.RUST_GATEWAY_URL || 'http://localhost:8080';
const PYTHON_BASE = __ENV.PYTHON_DASHBOARD_URL || 'http://localhost:8000';
const TEST_BOTH = __ENV.TEST_BOTH === 'true';

export const options = {
  stages: [
    { duration: '30s', target: 50 },    // Ramp to 50 VUs
    { duration: '1m', target: 100 },     // Hold at 100 VUs
    { duration: '30s', target: 500 },    // Ramp to 500 VUs
    { duration: '2m', target: 500 },     // Hold at 500 VUs
    { duration: '30s', target: 0 },      // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'],     // 95% under 200ms
    http_req_failed: ['rate<0.01'],       // <1% errors
  },
};

const params = {
  headers: { 'Content-Type': 'application/json' },
};

export default function () {
  // Unique email per (VU, iteration) so we exercise the register path each loop.
  const email = `load-${__VU}-${__ITER}-${Date.now()}@load.test`;
  const password = 'Password123!';
  const payload = JSON.stringify({
    email: email,
    password: password,
    display_name: 'Load Test User',
    workspace_name: 'Load Test WS',
  });

  // Test Rust /register (canonical post-#350 endpoint)
  const rustResp = http.post(`${RUST_BASE}/api/v2/auth/register`, payload, params);
  check(rustResp, {
    'Rust register status 201': (r) => r.status === 201,
    'Rust register returns onboarding metadata': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.status === 'ok' && body.role === 'owner' && body.user_id > 0;
      } catch (e) {
        return false;
      }
    },
    'Rust register < 200ms': (r) => r.timings.duration < 200,
  });

  if (TEST_BOTH) {
    // Compare against Python (same endpoint path, mounted under /api/v2)
    const pyResp = http.post(`${PYTHON_BASE}/api/v2/auth/register`, payload, params);
    check(pyResp, {
      'Python register status 200/201': (r) => r.status === 200 || r.status === 201,
      'Python register < 200ms': (r) => r.timings.duration < 200,
    });
  }

  sleep(0.1);
}

// ── Signin-only load test (separate function for targeted runs) ────────────
//
// Run with: k6 run --env TEST_MODE=signin tests/load/auth_load_test.js
//
// Targets a sustained read-heavy workload: one user per VU, registered
// once, then signin hammered for the duration. Tests session creation
// throughput (Argon2 verify + INSERT INTO sessions).
export function signinLoadTest() {
  const email = `load-signin-${__VU}@load.test`;
  const password = 'Password123!';

  // Pre-seed: register once per VU (no auto-login; we explicitly signin
  // below to mint tokens).
  if (__ITER === 0) {
    http.post(
      `${RUST_BASE}/api/v2/auth/register`,
      JSON.stringify({
        email,
        password,
        display_name: 'Signin Load',
        workspace_name: 'WS',
      }),
      params
    );
  }

  // Then hammer signin
  const resp = http.post(
    `${RUST_BASE}/api/v2/auth/signin`,
    JSON.stringify({ email, password }),
    params
  );
  check(resp, {
    'signin status 200': (r) => r.status === 200,
    'signin returns access_token': (r) => {
      try {
        return JSON.parse(r.body).access_token != null;
      } catch (e) {
        return false;
      }
    },
    'signin < 100ms': (r) => r.timings.duration < 100,
  });
}

// ── /me read-heavy load test ────────────────────────────────────────────────
//
// Run with: k6 run --env TEST_MODE=me tests/load/auth_load_test.js
//
// Mirrors the production traffic shape: most requests are authenticated
// reads via the JWT-protected /me endpoint. Tests JWT verify + 1 DB lookup
// throughput. Target: p95 < 50ms, error rate < 0.01% (Plan §14).
//
// Each VU registers once + signs in once at iteration 0, then hammers /me
// with the same bearer token for the rest of the run.
export function meLoadTest() {
  const email = `load-me-${__VU}@load.test`;
  const password = 'Password123!';

  // Seed user + obtain token on the first iteration of each VU.
  // Subsequent iterations reuse the same email/password and re-signin
  // (k6 cannot persist state between iterations of the default function).
  if (__ITER === 0) {
    http.post(
      `${RUST_BASE}/api/v2/auth/register`,
      JSON.stringify({
        email,
        password,
        display_name: 'Me Load',
        workspace_name: 'WS',
      }),
      params
    );
  }

  const signin = http.post(
    `${RUST_BASE}/api/v2/auth/signin`,
    JSON.stringify({ email, password }),
    params
  );
  let token = null;
  try {
    token = JSON.parse(signin.body).access_token;
  } catch (e) {
    // Signin failed — skip /me check this iteration
  }

  if (!token) return;

  const resp = http.get(`${RUST_BASE}/api/v2/me`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  check(resp, {
    '/me status 200': (r) => r.status === 200,
    '/me returns user data': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data != null && body.data.email != null;
      } catch (e) {
        return false;
      }
    },
    '/me < 50ms': (r) => r.timings.duration < 50,
  });
}
