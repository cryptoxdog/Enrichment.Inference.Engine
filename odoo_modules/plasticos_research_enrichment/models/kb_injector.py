class KBInjector:
    """Inject KB fragments into enrichment prompts based on predicted domains.

    Selects up to 3 KB records matching each predicted domain and returns
    their description text as a joined context block.
    """

    MAX_DOMAINS = 3

    @staticmethod
    def inject(env, partner, predicted_domains: list) -> str:
        kb_model = env["plasticos.inference.engine"]
        fragments = []

        for domain in predicted_domains[: KBInjector.MAX_DOMAINS]:
            records = kb_model.search([("domain", "=", domain)], limit=1)
            for r in records:
                fragments.append(r.description)

        return "\n".join(fragments)
