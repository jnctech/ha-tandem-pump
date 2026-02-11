# Branch History and Context

This document preserves the context of deprecated branches for future reference.

## v0.1.0.beta - DEPRECATED (Do Not Use)

**Status**: Failed attempts - superseded by v0.1.3-beta
**Created**: 2026-02-XX
**Deprecated**: 2026-02-11
**Contains**: 2 failed SSL fix attempts
**Root Issue**: Blocking SSL call in TandemSourceClient

### Problem Statement

The Tandem integration failed to load with error:
```
Detected blocking call to load_verify_locations with args (<ssl.SSLContext object>,
'/usr/local/lib/python3.13/site-packages/certifi/cacert.pem', None, None)
inside the event loop by custom integration 'carelink'
```

### Failed Attempt #1 (Commit 56ef0ce)

**Approach**: Use Home Assistant's `create_async_httpx_client` helper

**Changes**:
- Modified `tandem_api.py` to accept `hass` parameter in `__init__`
- Changed `_get_client()` to use `create_async_httpx_client(self.hass, timeout=30)`

**Result**: FAILED
- Caused "Invalid handler specified" error
- Integration completely broken
- Config flow would not load

**Why It Failed**:
Home Assistant's `create_async_httpx_client` creates a client with pre-configured settings that conflicted with the custom headers and follow_redirects needed for Tandem's OIDC flow.

### Failed Attempt #2 (Commits 6756f33, c4139aa)

**Approach**: Refactor client initialization with data dictionary

**Changes**:
- Attempted to restructure how client was initialized
- Added data dictionary pattern

**Result**: FAILED
- Still encountered the same SSL blocking issue
- Did not address root cause

**Why It Failed**:
Did not actually move SSL context creation out of the event loop. The blocking call to `load_verify_locations` still occurred synchronously.

### Successful Fix (v0.1.3-beta, Commit d028aab)

**Approach**: Use executor to offload SSL context creation

**Changes**:
```python
async def _get_client(self) -> httpx.AsyncClient:
    """Get or create the async HTTP client."""
    if self._client is None or self._client.is_closed:
        loop = asyncio.get_running_loop()
        ssl_ctx = await loop.run_in_executor(
            None,
            lambda: ssl.create_default_context(cafile=certifi.where()),
        )
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": USER_AGENT},
            verify=ssl_ctx,
        )
    return self._client
```

**Result**: SUCCESS
- SSL context creation offloaded to thread pool executor
- No blocking in event loop
- Maintains full control over httpx.AsyncClient configuration
- OIDC flow works correctly

### Lessons Learned

1. **Don't use Home Assistant helpers blindly**
   - `create_async_httpx_client` is useful for simple cases
   - Custom OAuth flows need manual client configuration

2. **Executor pattern for blocking I/O**
   - `asyncio.run_in_executor()` is the correct solution for unavoidable blocking calls
   - SSL context creation from disk is inherently blocking

3. **Test thoroughly before tagging**
   - v0.1.0.beta was tagged without full integration testing
   - v0.1.2.beta tag was on the broken branch

4. **Keep detailed logs**
   - ISSUES.MD in v0.1.0.beta branch documents the problem clearly
   - Helps future developers understand what went wrong

### Branch Commits (for reference)

```
v0.1.0.beta branch:
1d1aacb - Update ISSUES.MD (documents the problem)
c4139aa - Revise testing summary and analyze SSL error (tag: v0.1.2.beta)
6756f33 - Refactor client initialization with data dictionary (failed attempt #2)
56ef0ce - bug fix attempt #1 tandem_api to use Home Assistant's HTTP client (failed attempt #1)
1c3b584 - Results of initial testing (discovered the issue)
```

### Preservation

This branch is preserved in the repository for historical reference but should never be merged. The ISSUES.MD file in this branch contains valuable troubleshooting information.

**To view**:
```bash
git checkout v0.1.0.beta
cat ISSUES.MD
git checkout develop
```

## Future Branch Management

When a feature branch fails:
1. Document the failure in this file
2. Keep the branch in the repository (do not delete)
3. Mark as deprecated in branch description
4. Create new feature branch with lessons learned
5. Reference failed attempts in successful PR
