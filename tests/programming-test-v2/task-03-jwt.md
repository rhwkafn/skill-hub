# Task 3: JWT Authentication

Implement JWT token handling:
- generate_token(payload, secret, expiry_hours=24)
- verify_token(token, secret) → returns payload or raises
- Include iat, exp, iss claims
- Handle expired tokens, invalid signatures

Save to: `tests/programming-test-v2/solutions/jwt_auth.py`
