# 01 — VISION (implementation-invariant framing)
**Owner:** Program · **Source of truth:** Vision (frozen) · **Status:** reference

> This card exists so implementers share the *why*. It changes no architecture. It exists to resolve judgment calls in the implementer's favor when a spec is silent: when in doubt, choose the option that best serves the invariants below.

## What Charter House is
A machine that converts one founder's **attention** into validated, revenue-earning software ventures — repeatedly, cheaply, and without betting everything on any single idea, model, provider, or tool.

## The three things the software exists to protect
1. **Signal is the scarce input.** The system's purpose is to buy real-world signal (replies, visitors, signups, payments) at the lowest cost per verdict. Implication for code: cheap/async-by-default; token cost is accounted (telemetry); nothing wastes founder time.
2. **Founder attention is the scarce internal resource.** Not compute, not models. Implication: the software spends the human only at gates and RED actions; everything else is automated and triaged.
3. **The machine compounds; ventures are expendable.** Every venture, alive or dead, deposits a reusable asset. Implication: memory is first-class; kills must bank assets; knowledge tiers up over time.

## The two seams that must never fuse (architectural integrity)
- **Model-provider seam:** capabilities name *roles*, never models. Swapping any model/provider is config-only.
- **Agent-runtime seam:** the doctrine/lifecycle live in vendor-neutral form; the harness (OpenCode) is replaceable.

## Implementer's tie-breaker
When a specification permits two implementations, pick the one that (in priority order) better: preserves an invariant → removes an ambiguity → increases subsystem independence → reduces future refactoring → is faster. Speed is last.
