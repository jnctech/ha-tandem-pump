# Release Process

This document describes the process for releasing new versions of the Tandem Source / Carelink integration.

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR.MINOR.PATCH** for stable releases (e.g., 1.0.0)
- **MAJOR.MINOR.PATCH-beta** for beta releases (e.g., 0.1.3-beta)
- **MAJOR.MINOR.PATCH-alpha** for alpha releases (e.g., 0.1.0-alpha)

### When to Increment

- **MAJOR**: Breaking changes, incompatible API changes
- **MINOR**: New features, backward-compatible functionality
- **PATCH**: Bug fixes, backward-compatible fixes
- **Pre-release suffix**: Unstable or testing versions

## Release Checklist

### Pre-Release (1-2 days before)

- [ ] All feature branches merged to `develop`
- [ ] All tests passing locally and in CI
- [ ] Code review completed
- [ ] Documentation updated (README.md, docstrings)
- [ ] CHANGELOG.md updated with all changes
- [ ] Version bumped in:
  - [ ] `custom_components/carelink/manifest.json`
  - [ ] `VERSION` file
  - [ ] `CHANGELOG.md` (unreleased → versioned)

### Release Day

1. **Verify develop branch**
```bash
git checkout develop
git pull origin develop
pytest tests/  # All tests must pass
```

2. **Update CHANGELOG.md**
   - Move changes from [Unreleased] to new version section
   - Add release date
   - Update comparison links at bottom

3. **Commit version changes**
```bash
git add custom_components/carelink/manifest.json VERSION CHANGELOG.md
git commit -m "chore: Prepare release v0.1.3-beta"
git push origin develop
```

4. **Create and push tag**
```bash
git tag -a v0.1.3-beta -m "Release v0.1.3-beta"
git push origin v0.1.3-beta
```

5. **Create GitHub Release**
   - Go to: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/releases/new
   - Tag: Select `v0.1.3-beta`
   - Title: `v0.1.3-beta - [Brief Description]`
   - Description: Copy relevant section from CHANGELOG.md
   - Check "This is a pre-release" for beta/alpha versions
   - Publish release

### Post-Release

1. **Create release notes issue**
   - Document any known issues
   - Request testing feedback from users
   - Link to installation instructions

2. **Monitor for issues**
   - Watch GitHub issues
   - Monitor Home Assistant logs forum
   - Be ready to hotfix critical bugs

3. **Update CHANGELOG.md**
   - Add new [Unreleased] section at top

## Hotfix Process

For critical bugs in a released version:

1. **Create hotfix branch from tag**
```bash
git checkout -b hotfix/critical-bug-name v0.1.3-beta
```

2. **Fix the bug**
   - Make minimal changes
   - Add tests
   - Update CHANGELOG.md

3. **Bump PATCH version**
   - `0.1.3-beta` → `0.1.4-beta`

4. **Merge to develop and create tag**
```bash
git checkout develop
git merge hotfix/critical-bug-name
git tag -a v0.1.4-beta -m "Hotfix: [description]"
git push origin develop --tags
```

5. **Create GitHub release** (as above)

## Beta → Stable Transition

When a beta version is ready for stable release:

1. **Comprehensive testing**
   - All known issues resolved
   - Tested on multiple HA versions
   - User feedback reviewed

2. **Remove pre-release suffix**
   - `0.1.3-beta` → `0.1.3`

3. **Follow standard release process**

4. **Update HACS default**
   - Ensure HACS shows stable release by default

## Branch Cleanup

After release, clean up merged feature branches:

```bash
# List merged branches
git branch --merged develop

# Delete local branches
git branch -d feature/branch-name

# Delete remote branches
git push origin --delete feature/branch-name
```

## Emergency Rollback

If a release causes critical issues:

1. **Create new release from previous tag**
```bash
git tag -a v0.1.5-beta -m "Rollback to v0.1.3-beta" v0.1.3-beta
git push origin v0.1.5-beta
```

2. **Create GitHub release** marking it as rollback
3. **Document issues** in CHANGELOG.md
4. **Fix in develop** and prepare new release
