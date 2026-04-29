# Open Questions for the Thursday Call

Things to nail down with Nitin before we start cutting code on M0/M1.
Numbered so we can walk through them quickly.

## Scope / product

1. **One repo or two?** Right now `convaix/` and `VectorDatabaseBook/` are
   separate. The plan keeps work inside `convaix/` and treats the book repo
   as read-only reference. Confirm, or do you want a third "app" repo?

2. **Author handle.** convaix's `x-convaix.author.handle` is a free text
   field. For the local-first demo, default to `$USER`. For the hub later,
   we'll need real identities. Is GitHub-handle-as-author OK for v1?

3. **Demo audience.** Who is the demo for? An investor / a partner / your
   own dogfooding? Affects how much polish M3 needs.

4. **The "social network" piece.** The chat references a hub for sharing
   conversations. Is that on the roadmap before or after the desktop ship?
   Plan currently parks it post-M5.

5. **Pricing.** Day-one $25–30 price point — confirm. Trial duration?

## Technical

6. **Embedding model: nomic-embed-text-v1.5 at 768-dim?** convaix already
   uses this. Plan locks it in. Veto?

7. **Embedding fallback.** convaix today only runs on Apple Silicon (MLX).
   Plan adds `sentence-transformers` for cross-platform. OK to accept the
   ~2 GB torch dependency, or do we need a lighter fallback (gguf /
   llama.cpp)?

8. **Postgres or SQLite first?** Chat says "first PG, then SQLite". SQLite
   already works in convaix, so plan adds PG (M2) without removing SQLite.
   Confirm that's the read.

9. **Ollama dependency.** RAG (M4) assumes local Ollama. The desktop bundle
   will not include Ollama (too big, license complexity). Acceptable that
   RAG is "soft-required" — works if Ollama is installed, falls back to a
   "not configured" state otherwise? Or do you want a paid OpenAI / Claude
   API path bundled in?

10. **Provider order.** Plan does Claude → ChatGPT → Gemini in that order.
    Any reason to flip?

11. **Re-import semantics.** If the user re-exports their Claude data and
    re-imports, do they want a new snapshot (history preserved) or
    upsert-by-conv_id (latest wins)? Plan currently does "new snapshot"
    via convaix's existing model — fine?

12. **Branching in ChatGPT exports.** The export is a tree; convaix v1.0 is
    a flat list. Plan flattens by following the current leaf and stashes
    branches in `metadata`. Acceptable, or do you want full branch support
    in v1.0+?

## Packaging (M5, but want a directional read now)

13. **PyInstaller+pywebview vs Tauri sidecar.** Plan recommends
    PyInstaller+pywebview for the first build, Tauri later. OK to defer
    the Tauri call?

14. **Code signing budget.** Apple Dev ID ($99/yr), Windows EV cert
    ($300+/yr). Who pays?

15. **Distribution channel.** GitHub Releases for v1 (free, simple), or
    do you want the Mac App Store / Microsoft Store?

## Process

16. **Working cadence.** Async via this repo + occasional calls? Anything
    on Slack / Discord / email?

17. **Branching model.** PRs into `main`, or trunk-based? Convaix today
    has no branching convention.

18. **Test infra.** Local-only for now, or do you want CI (GitHub Actions)
    set up early? CI matters for M2 (testing PG path) but not before.

## "Nice to have" deferrals

These are mentioned in the chat but not in the milestone plan. Noting so
we don't lose them:

- Browser extension (you said "extracting is the easy part" — agreed,
  not doing one).
- Common embedding/RAG bridge across all three LLMs in one chat (this is
  exactly M4, just naming it).
- Annotations / public commentary on shared conversations (tables exist
  in convaix; UI deferred until post-demo).
- Conversation signatures (`x-convaix.signature` is a placeholder in the
  schema; only relevant when we federate).
