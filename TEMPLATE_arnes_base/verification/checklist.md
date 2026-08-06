# Verification Checklist — before calling a new instance "done"

1. **Mechanical equivalence, if migrating existing code:** run before
   and after, diff the outputs numerically (not by eye). This is how
   the F1 migration was verified — `load`/`attention`/every channel
   column compared with `np.allclose` / exact match, not inspection.

2. **CHANNELS costs are declared, not copied.** If any value matches
   F1's by coincidence, write down why it's actually right for this
   domain, not just convenient.

3. **HAS_RECOVERY_WINDOW and HAS_MULTI_TIMESCALE_LOAD are set**, not
   left as None. Both have real consequences downstream (queue
   usefulness, load_model shape) — see CONTRACT.md.

4. **Run the Voice-admission check from the F1 finding:** with this
   domain's real tuned costs, does a fresh Voice request (nothing
   queued) get admitted at this domain's most-open realistic moment?
   Know the answer on purpose — don't find out by accident later.

5. **Every load input is labeled** REAL / PROXY / DECLARED. No
   unlabeled numbers feeding the governance decision.

6. **Reflex trigger is either implemented or explicitly declared
   absent** (HAS_REFLEX = False) — never left as an unnoticed stub.
