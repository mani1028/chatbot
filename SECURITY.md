# Security Notes and Recommendations

## Password Security
- Passwords are hashed using Werkzeug security utilities.
- Never store or log plaintext passwords.
- Enforce strong password policies for admin and client accounts.

## Session Management
- Use secure, random `SECRET_KEY` in production.
- Set `SESSION_COOKIE_SECURE` and `SESSION_COOKIE_HTTPONLY` in production.
- Consider enabling CSRF protection for all admin and sensitive routes.

## Rate Limiting
- Use `flask-limiter` to prevent brute-force and abuse on login and admin endpoints.

## Domain Whitelisting
- The `Site` model supports `domain_whitelist` to restrict widget embedding to approved domains.

## Environment Variables
- Never commit secrets or credentials to version control.
- Use `.env` for local development and environment variables for production.

## Dependency Management
- Keep all dependencies up to date and monitor for vulnerabilities.

## Logging and Auditing
- Use the `AuditLog` model to track admin actions and sensitive changes.

## Additional Recommendations
- Regularly review and update dependencies.
- Perform periodic security audits and penetration testing.
- Document all security-related configuration for future maintainers.
