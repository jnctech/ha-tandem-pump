## Summary
<!-- What changed and why — one bullet per logical change group -->
-

## Test Plan
<!-- Checklist of what to verify after merge/deploy -->
- [ ] `pytest tests/ -v` passes 100%
- [ ] `python -m ruff format --check custom_components/carelink tests` clean
- [ ] `bandit -c bandit.yaml -r custom_components/carelink` clean
- [ ] Deployed to HA instance and verified sensors load correctly
- [ ] Statistics Graph cards unaffected (if LTS code changed)

## Post-Deploy Actions
<!-- Steps the user must take after merging — secrets, integrations, restarts -->
- None / <!-- or list steps -->

## Checklist
- [ ] Branch is up to date with `develop`
- [ ] `docs/CHANGE-REGISTER.md` updated (new CR entry if significant)
- [ ] `docs/ISSUES.md` updated (status updated for resolved issues)
- [ ] `docs/decisions/` updated if an architecture decision changed
- [ ] README / CONTRIBUTING updated if needed
