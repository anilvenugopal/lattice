# Prompt for the Taskline project

Copy `taskline-requirements.md` into the Taskline repository (for example as
`docs/lattice_integration.md`), then give the Taskline session this prompt:

---

Lattice, a separate platform project, will build the Taskline admin UI as its
own app, `lattice-taskline`. That answers our open question 2 in
`docs/product_requirement.md`: the UI is not part of this package. What Lattice
needs from Taskline to build it is in `docs/lattice_integration.md`.

Please do the following, and **do not change any code yet**:

1. **Read** `docs/lattice_integration.md` alongside our own
   `docs/product_requirement.md`, `docs/architecture.md` and
   `docs/product_development_plan.md`.

2. **Gap analysis.** For each numbered item in the integration document, say:
   - what Taskline already has (with file and function names);
   - what is missing or different;
   - whether it conflicts with our requirements or architecture, and how you
     would resolve it.

   Pay particular attention to:
   - **the read views** (section 2): a `taskline_api` schema of stable, indexed,
     read-only views as our public read contract;
   - **the command API** (section 3): `cancel_run`, `retry_run`, `requeue` and
     `submit_job` as plain async functions with an `actor` and typed results,
     which the CLI then calls;
   - **run events** (section 5): readable by a monotonic id, in a
     CloudEvents-shaped view, because our hooks fire in worker processes and
     cannot reach the web process.

3. **Propose changes to our documents:**
   - new or changed requirements in `docs/product_requirement.md`, numbered in
     our style;
   - the architecture changes in `docs/architecture.md`: the public contract,
     the `taskline_api` views, the command module, typed job inputs, and the
     event view;
   - an updated `docs/product_development_plan.md` that places this work. The
     "Must" items should come early enough that the Lattice app can start
     against a released version.

   Show these as proposed changes for my approval. Don't apply them yet.

4. **Questions.** List anything in the integration document you disagree with
   or need decided, with your recommendation for each. Lattice adapts where
   Taskline has a better answer. The goal is a contract both sides can keep.

Ground rules:
- Keep Taskline independent: it must not import or depend on Lattice.
- Everything Lattice may use goes into one written public contract
  (`docs/public_contract.md`), with a test that fails when a listed name or
  view column disappears.
- Follow our existing conventions in `CLAUDE.md` and the docs.
