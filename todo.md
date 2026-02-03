# Production Readiness TODO

## Critical (Before Launch)

- [ ] **Redeploy with wallet fix** - Run `docker-compose down && docker-compose up -d` on server to apply volume mount fix
- [ ] **Create production wallet** - Create Monero wallet via RPC after redeployment
- [ ] **Test real order flow** - Place a test order with real XMR to verify payment detection works
- [ ] **Secrets management** - Move sensitive data from `.env` to Docker secrets or a vault solution
- [ ] **Database backups** - Set up automated MySQL backups (daily cron + offsite storage)

## High Priority (Soon After Launch)

- [ ] **Wallet backup** - Export and securely store wallet seed/keys
- [ ] **Monitoring** - Set up uptime monitoring for bot and health endpoint
- [ ] **Alerting** - Configure alerts for failed payments, errors, low wallet balance
- [ ] **Log aggregation** - Centralize logs (e.g., Loki, ELK stack, or cloud logging)

## Medium Priority

- [ ] **SSL/HTTPS** - Add SSL termination for health check endpoint
- [ ] **Rate limiting** - Protect against abuse/spam
- [ ] **Crypto swap integration** - Replace mock swap service with real provider (Trocador/ChangeNow) for BTC/ETH/SOL support
- [ ] **Connection pooling** - Optimize database connections for higher load

## Nice to Have

- [ ] **Prometheus metrics** - Export metrics for Grafana dashboards
- [ ] **Graceful degradation** - Better fallback behavior when external services fail
- [ ] **Input sanitization audit** - Review all user inputs for security
- [ ] **Load testing** - Verify performance under expected load
