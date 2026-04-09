import http from 'k6/http';
import { check, sleep } from 'k6';

// The 3-Minute Spike Configuration
export const options = {
    stages:[
        { duration: '30s', target: 10 },  // Ramp up to 10 VUs
        { duration: '60s', target: 10 },  // Hold at 10 VUs (Baseline)
        { duration: '30s', target: 25 },  // Ramp to 25 VUs (Stress)
        { duration: '60s', target: 25 },  // Hold at 25 VUs
        { duration: '20s', target: 50 },  // Spike to 50 VUs (Breaking Point)
        { duration: '10s', target: 0 },   // Cool down
    ],
    thresholds: {
        http_req_failed:['rate<0.05'],   // We want < 5% errors
    },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const TEST_MODE = __ENV.TEST_MODE || 'warm'; 
const USERNAME = __ENV.TEST_USER || 'tester1'; // Use a user you registered!
const PASSWORD = __ENV.TEST_PASS || 'super_secret_passwordLALALA';

// 1. Setup: Runs once per VU to get the JWT token
export function setup() {
    const res = http.post(`${BASE_URL}/auth/login`, {
        username: USERNAME,
        password: PASSWORD,
    });
    return { token: res.json('access_token') };
}

// 2. The Execution Loop
export default function (data) {
    let query = "Does the bank have adequate exit strategies for vendors?";

    if (TEST_MODE === 'cold') {
        // TRUE CACHE BUSTING: Makes every single query mathematically unique
        // Example: "... vendors? (Trace: 4-12)"
        query += ` (Trace: ${__VU}-${__ITER})`;
    }

    const payload = JSON.stringify({
        query: query,
        policy_id: null,
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${data.token}`,
        },
        timeout: '30s', // 30 second timeout
    };

    const res = http.post(`${BASE_URL}/audit`, payload, params);

    check(res, {
        'status is 200': (r) => r.status === 200,
        'no internal errors': (r) => r.status !== 500,
        'not rate limited': (r) => r.status !== 429,
    });

    // 1-second think time between requests
    sleep(1);
}