# 🚀 Enrichment API — Launch Checklist

## Phase 1: Local Dev (30 min)
- [ ] Copy `.env.example` → `.env`, fill in `PERPLEXITY_API_KEY`
- [ ] Generate client API key: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] Hash it: `echo -n "YOUR_KEY" | sha256sum | awk '{print $1}'` → put in `API_KEY_HASH`
- [ ] `docker compose -f docker-compose.dev.yml up -d`
- [ ] Verify: `curl http://localhost:8000/api/v1/health`
- [ ] Test enrich: `curl -X POST http://localhost:8000/api/v1/enrich -H "X-API-Key: YOUR_KEY" -H "Content-Type: application/json" -d '{"entity":{"partner_name":"Tesla"},"object_type":"Lead","objective":"Research"}'`

## Phase 2: Odoo Integration (15 min)
- [ ] Open Odoo at `http://localhost:8069`
- [ ] Activate developer mode
- [ ] Go to Apps → Update Module List
- [ ] Search "Enrichment Bridge" → Install
- [ ] Go to Settings → General → Enrichment API section
- [ ] Set API URL: `http://enrichment-api:8000/api/v1`
- [ ] Set API Key: (the client key you generated, NOT the hash)
- [ ] Create a test lead in CRM
- [ ] Click 🔬 Enrich button on the lead
- [ ] Check the Enrichment tab → see the run log
- [ ] Verify enriched fields were filled

## Phase 3: Batch Test (10 min)
- [ ] Create 5+ leads with just company names
- [ ] Enable "Auto-Enrich" in Settings
- [ ] Trigger cron manually: Settings → Technical → Scheduled Actions → "Enrichment: Batch Enrich New Leads" → Run Manually
- [ ] Check Enrichment → Enrichment Runs for batch results
- [ ] Verify leads now have enriched data

## Phase 4: Deploy to Kubernetes (20 min)
- [ ] Build + push image: `docker build -t ghcr.io/cryptoxdog/enrichment-api:v2.2.0 . && docker push ghcr.io/cryptoxdog/enrichment-api:v2.2.0`
- [ ] Run validation: `./deploy/scripts/validate.sh`
- [ ] Create secrets: `./deploy/scripts/generate-secrets.sh enrichment pplx-YOUR-KEY`
- [ ] Deploy: `./deploy/scripts/deploy.sh production kustomize`
- [ ] Verify pods: `kubectl get pods -n enrichment`
- [ ] Test via port-forward: `kubectl port-forward svc/enrichment-api 8000:8000 -n enrichment`

## Phase 5: Connect Production Odoo (5 min)
- [ ] In production Odoo: Settings → Enrichment API
- [ ] Set URL to `https://enrichment-api.yourdomain.com/api/v1`
- [ ] Set API Key (client key from generate-secrets.sh output)
- [ ] Test with one real lead
- [ ] Enable auto-enrich cron
- [ ] 🎉 Done — leads auto-enrich every 4 hours

## Monitoring
- [ ] Check enrichment run logs in Odoo: Enrichment → Enrichment Runs
- [ ] Check API health: `GET /api/v1/health`
- [ ] Check pod status: `kubectl get pods -n enrichment -w`
- [ ] Check logs: `kubectl logs -n enrichment -l app=enrichment-api --tail=100 -f`
