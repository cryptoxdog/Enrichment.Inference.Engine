import asyncio

from .entropy_engine import EntropyEngine
from .extraction_engine import ExtractionEngine
from .inference_bridge import InferenceBridge
from .perplexity_client import PerplexityClient
from .synthesis_engine import SynthesisEngine

MIN_VALID = 2
MAX_CONCURRENCY = 3


async def process_run(env, run) -> None:
    """End-to-end async enrichment pipeline for a single enrichment run record.

    1. Compute entropy to determine variation count (3–5 calls)
    2. Fan out concurrent Perplexity queries with semaphore limit
    3. Validate and filter responses
    4. Synthesize valid payloads
    5. Apply results via InferenceBridge
    """
    api_key = env["ir.config_parameter"].sudo().get_param("perplexity.api_key")
    client = PerplexityClient(api_key)

    partner = run.partner_id
    entropy = EntropyEngine.compute(partner)
    variation_count = min(5, max(3, entropy))

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def call() -> dict:
        async with semaphore:
            prompt = (
                f"Enrich partner:\n"
                f"Name: {partner.name}\n"
                f"Country: {partner.country_id.name if partner.country_id else ''}\n"
                f"Return strictly valid JSON."
            )
            return await client.query(prompt)

    tasks = [call() for _ in range(variation_count)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    valid = [r for r in results if isinstance(r, dict) and ExtractionEngine.validate(r)]

    if len(valid) < MIN_VALID:
        run.state = "failed"
        return

    synthesis = SynthesisEngine.synthesize(valid)
    run.final_confidence = synthesis["confidence"]
    run.state = "synthesized"

    InferenceBridge.apply(env, partner, synthesis)

    run.state = "applied"
