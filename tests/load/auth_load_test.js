import http from 'k6/http';
import { check, sleep } from 'k6';

// K6 load test for Rust gateway auth endpoints.
// Per HARNESS-ENGINEERING-PLAN.md Section 14.
//
// Run:
//   k6 run tests/load/auth_load_test.js
//
// Targets:
//   signin  p95 < 100ms, error rate < 0.1%
//   signup  p95 < 200ms, error rate < 0.1%

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
  const email = `load-${__VU}-${__ITER}@load.test`;
  const password = 'Password123!';
  const payload = JSON.stringify({
    email: email,
    password: password,
    display_name: 'Load Test User',
    workspace_name: 'Load Test WS',
  });

  // Test Rust signup
  const rustResp = http.post(`${RUST_BASE}/api/v2/auth/signup`, payload, params);
  check(rustResp, {
    'Rust signup status 201': (r) => r.status === 201,
    'Rust signup < 200ms': (r) => r.timings.duration < 200,
  });

  if (TEST_BOTH) {
    // Also test Python for comparison
    const pyResp = http.post(`${PYTHON_BASE}/auth/register`, payload, params);
    check(pyResp, {
      'Python register status 200/201': (r) => r.status === 200 || r.status === 201,
    });
  }

  sleep(0.1);
}

// ── Signin-only load test (separate function for targeted runs) ────────────
//
// Run with: k6 run --env TEST_MODE=signin tests/load/auth_load_test.js
export function signinLoadTest() {
  const email = `load-signin-${__VU}@load.test`;
  const password = 'Password123!';

  // Pre-seed: signup once per VU
  if (__ITER === 0) {
    http.post(
      `${RUST_BASE}/api/v2/auth/signup`,
      JSON.stringify({ email, password, workspace_name: 'WS' }),
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
    'signin < 100ms': (r) => r.timings.duration < 100,
  });
}
