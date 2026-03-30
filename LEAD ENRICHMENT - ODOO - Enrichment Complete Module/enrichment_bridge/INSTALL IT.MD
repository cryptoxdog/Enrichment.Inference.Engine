Install It
Drop the enrichment_bridge/ folder into your Odoo addons path and install via CLI — no UI required:

bash
# From docker-compose
docker compose exec odoo odoo -d YOUR_DB -i enrichment_bridge --stop-after-init

# Or on bare metal
./odoo-bin -d YOUR_DB -i enrichment_bridge --stop-after-init
The ZIP download above contains the exact file structure Odoo 19 expects. Unzip it straight into your extra-addons/ directory and you're live
