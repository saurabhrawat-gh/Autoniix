import http from 'k6/http';
import { check, sleep } from 'k6';


const RUST_BASE = __ENV.RUST_GATEWAY_URL || 'http://localhost:8080';
const PYTHON_BASE = __ENV.PYTHON_DASHBOARD_URL || 'http://localhost:8000';
const TEST_BOTH = __ENV.TEST_BOTH === 'true';

export const options = {
  stages: [
    { duration: '30s', target: 50 },
    { duration: '1m', target: 100 },
    { duration: '30s', target: 500 },
    { duration: '2m', target: 500 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<200'],
    http_req_failed: ['rate<0.01'],
  },
};

const params = {
  headers: { 'Content-Type': 'application/json' },
};

export default function () {
  const email = `load-${__VU}-${__ITER}-${Date.now()}@load.test`;
  const password = 'Password123!';
  const payload = JSON.stringify({
    email: email,
    password: password,
    display_name: 'Load Test User',
    workspace_name: 'Load Test WS',
  });

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
    const pyResp = http.post(`${PYTHON_BASE}/api/v2/auth/register`, payload, params);
    check(pyResp, {
      'Python register status 200/201': (r) => r.status === 200 || r.status === 201,
      'Python register < 200ms': (r) => r.timings.duration < 200,
    });
  }

  sleep(0.1);
}

export function signinLoadTest() {
  const email = `load-signin-${__VU}@load.test`;
  const password = 'Password123!';

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

export function meLoadTest() {
  const email = `load-me-${__VU}@load.test`;
  const password = 'Password123!';

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
