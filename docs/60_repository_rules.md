# 60 — REPOSITORY RULES (hygiene + ownership enforcement)
**Owner:** Program · **Source of truth:** `30`, `51` · **Status:** authoritative

## One-owner rule (hard)
Every file and directory has exactly one owning implementation agent (map in `51` + `30`). A PR that modifies files outside the author-agent's ownership **fails the merge gate** (`63`). Shared types live only in `contracts\` (Interface Agent); no duplication elsewhere.

## No overlapping responsibility
- A rule is enforced in exactly one subsystem (the owner). Duplicating a rule in the Conductor is an `INV-COND-1` violation.
- If two agents "need" the same logic, it belongs in `contracts\` or a shared owned module, imported — never copied.

## File discipline
- No secrets, no PII, no `*.private.md` content committed (CI secret+PII scan blocks it).
- No generated artifacts committed except intended ones (`AGENTS.md`, config examples). Weights/vectors/logs are external (`.gitignore`).
- Each subsystem folder carries its four contract docs (`56`) and keeps them current with the code (`62`).

## Change scope
- One subsystem per PR (default). Cross-subsystem changes require an ICR (`43`) and both owners' sign-off.
- Interface changes follow the ICR protocol (`43` §4); a `40`/`contracts` change without an ICR fails CI.

## Dependency hygiene
- Import graph must match the allowed DAG (`43` §8); a forbidden import fails CI (e.g., `lifecycle` importing `router`).
- Third-party deps are minimal, pinned, and open-source (frozen preference). New deps require a note in the subsystem `RISKS.md`.

## Ownership audit
The manifest ownership table (`00`) is the source of truth for ownership; CI cross-checks changed paths against it. Adding a new file requires assigning an owner in the same PR.
