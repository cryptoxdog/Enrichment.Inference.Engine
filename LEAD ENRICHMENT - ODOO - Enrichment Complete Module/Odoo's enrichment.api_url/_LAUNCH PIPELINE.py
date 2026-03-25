# ── Phase 1: Local stack (one command) ───────────
cp .env.example .env
# Fill in PERPLEXITY_API_KEY, generate API_KEY_HASH
docker compose -f docker-compose.dev.yml up -d
# This starts: enrichment-api + redis + odoo + postgres

# ── Phase 2: Install Odoo module (via CLI, no UI) ──
docker compose exec odoo odoo -d odoo -i enrichment_bridge --stop-after-init

# ── Phase 3: Configure via xmlrpc (no UI) ──────────
python3 -c "
import xmlrpc.client
url = 'http://localhost:8069'
db, user, pw = 'odoo', 'admin', 'admin'
uid = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common').authenticate(db, user, pw, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
# Set API config
models.execute_kw(db, uid, pw, 'ir.config_parameter', 'set_param',
    ['enrichment.api_url', 'http://enrichment-api:8000/api/v1'])
models.execute_kw(db, uid, pw, 'ir.config_parameter', 'set_param',
    ['enrichment.api_key', 'YOUR-CLIENT-API-KEY'])
models.execute_kw(db, uid, pw, 'ir.config_parameter', 'set_param',
    ['enrichment.auto_enrich', 'True'])
print('✅ Enrichment configured')
"

# ── Phase 4: Create a test lead + enrich it ──────
python3 -c "
import xmlrpc.client
url = 'http://localhost:8069'
db, user, pw = 'odoo', 'admin', 'admin'
uid = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common').authenticate(db, user, pw, {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
# Create lead
lead_id = models.execute_kw(db, uid, pw, 'crm.lead', 'create', [{
    'name': 'Test Enrichment — Acme Corp',
    'partner_name': 'Acme Corporation',
    'email_from': 'hello@acme.com',
    'type': 'lead',
}])
# Trigger enrichment
models.execute_kw(db, uid, pw, 'crm.lead', 'action_enrich', [[lead_id]])
# Read back
lead = models.execute_kw(db, uid, pw, 'crm.lead', 'read', [[lead_id],
    ['name','enrichment_state','last_enrichment_confidence','website','phone','city']])
print(lead)
"

# ── Phase 5: E2E tests ──────────────────────────
pytest tests/test_e2e_odoo.py -v
