<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# What’s the lowest hanging fruit I can implement the fastes and easiest with most benefit ?

The single fastest win is **three training-level changes you can ship in 1–2 days** that require zero architecture changes and yield a combined ~8–12% relative improvement in link prediction quality. After that, CompGCN is the first real architectural upgrade worth the effort.

## Tier 0: Ship This Week (Hours, Not Days)

These are code-level changes to your **existing** CompoundE3D training loop — no new modules, no new dependencies, no interface changes:

### 1. Self-Adversarial Negative Sampling (SANS)

Replace your current uniform negative sampling with RotatE's self-adversarial loss:[^1]

```python
# ONE function replacement in your training loop
def sans_loss(pos_score, neg_scores, gamma=12.0, alpha=1.0):
    weights = F.softmax(alpha * neg_scores, dim=-1).detach()
    pos_loss = -F.logsigmoid(gamma - pos_score)
    neg_loss = -(weights * F.logsigmoid(neg_scores - gamma)).sum(dim=-1)
    return (pos_loss + neg_loss).mean()
```

Hard negatives (entities your model *almost* confuses for the real answer) get higher weight, forcing the model to learn fine-grained distinctions between similar HDPE recyclers or PP processors. Published gain: **+3–5% MRR** across all architectures with zero parameter increase.[^1]

### 2. Edge Dropout During Training

One line addition before your message-passing or scoring step:[^1]

```python
# During training only: drop edges connecting query (h,r,t) pairs
if self.training:
    mask = torch.rand(edge_index.size(1)) > 0.1  # p=0.1 dropout
    edge_index = edge_index[:, mask]
    edge_type = edge_type[mask]
```

This forces the model to learn through longer-range structural patterns instead of shortcutting via direct edges. NBFNet's ablation shows this single trick accounts for **+4.7% relative HITS@10**.[^1]

### 3. Filtered Ranking Evaluation

You currently have no public benchmark metrics — this is a blocker for measuring anything else. Implement the standard filtered ranking protocol from NBFNet §4.1: remove all known-true triples from the candidate set except the query triple, then compute MRR and HITS@{1,3,10}. Takes a few hours to implement, gives you a baseline number to measure every subsequent improvement against.[^2][^1]

**Combined Tier 0 impact**: ~8–12% relative MRR improvement + measurement infrastructure. Zero architecture changes. Deployable in 1–2 days.

***

## Tier 1: First Real Architecture Win (2–3 Weeks)

### CompGCN Encoder with Basis Decomposition

This is the **highest ROI architectural upgrade** across all five papers. Your current stack uses static embedding lookup tables for entities and relations — CompGCN replaces these with a graph-structure-aware encoder that jointly learns entity and relation representations via circular correlation composition.[^2][^1]

**Why it matters for L9 specifically:**

- Your ENRICH convergence loop **discovers new entities continuously** (new facilities, new material grades, new contamination profiles). Static lookup tables cannot represent these without retraining. CompGCN generates embeddings from neighborhood structure, so a newly discovered Tier-2 HDPE recycler inherits a meaningful representation immediately from its connections.[^1]
- Basis decomposition with B=50 reduces your relation parameter count by **4.74×** while losing <1% MRR — critical since your plastics vertical has 200–500 relations.[^1]
- Published MRR: **0.355 on FB15k-237** with ConvE scoring (+5% over RotatE baseline).[^1]

**What changes in your codebase:**


| Component | Before | After |
| :-- | :-- | :-- |
| Entity encoder | `E[entity_id]` static lookup | `CompGCN.forward(graph)` structural |
| Relation encoder | `R[relation_id]` static lookup | Joint update via `z_r = W_rel · z_r` |
| Parameter count (500 relations) | ~20M params | ~4.2M params (B=50) |
| New entity handling | Retrain required | Zero-shot from neighbors |

**Composition operator**: Use **circular correlation** (`Corr`) — consistently +1–2% MRR over subtraction and Hadamard in CompGCN's ablation across all scoring functions.[^1]

***

## Tier 2: The Transformative Upgrade (6–8 Weeks After Tier 1)

### NBFNet Bellman-Ford Core Loop

This is where you get **multi-hop reasoning + path interpretability + full inductive generalization**, but it depends on Tier 1 (CompGCN provides the relation embeddings that initialize NBFNet's edge weights). Don't start this until CompGCN is validated.[^1]

***

## Priority Stack Summary

| Priority | What | Effort | Impact | Paper |
| :-- | :-- | :-- | :-- | :-- |
| **🔴 Do Monday** | SANS loss function | 1 hour | +3–5% MRR | KGE Overview |
| **🔴 Do Monday** | Edge dropout (p=0.1) | 30 min | +4.7% HITS@10 | NBFNet |
| **🔴 Do Monday** | Filtered MRR/HITS@N eval | 4 hours | Measurement baseline | NBFNet §4.1 |
| **🟡 Week 2–4** | CompGCN encoder (Corr + B=50) | 2–3 weeks | +5% MRR + inductive | CompGCN |
| **🟡 Week 2–4** | AGEA response sanitization | 2 days | Security blocker closed | AGEA §4.3 |
| **🔵 Week 5–12** | NBFNet Bellman-Ford loop | 6–8 weeks | +15–21% HITS@1 + paths | NBFNet |

The AGEA response sanitization (strip entity IDs from your GRAPH API responses) is also trivially fast — a single middleware function — and given your API is public-facing, it's a **security blocker** that should ship alongside the Tier 0 training fixes. Your current API returns full `(h, r, t)` triples with entity metadata, which is direct AGEA attack surface (90–96% graph recovery under 1K queries).[^2][^1]

Bottom line: **SANS + edge dropout + filtered eval on Monday. CompGCN encoder over the next 2–3 weeks. Everything else follows.**
<span style="display:none">[^3]</span>

<div align="center">⁂</div>

[^1]: how-does-the-below-relate-to-t-mrlEYegUSB.ln2d.E2MRSw.md

[^2]: graph-repo-development-yvPwwEF_SyiqKAFuAiO7AA.md

[^3]: lead-enrichment-fastapi-jSFev7y4TxaCfHtXCv7_Pw.md
