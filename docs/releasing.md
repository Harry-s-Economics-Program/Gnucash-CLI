# Releasing

The PyPI Trusted Publishing environment name is:

```text
pypi
```

Configure PyPI Trusted Publishing with:

- Owner: `Harry-s-Economics-Program`
- Repository: `Gnucash-CLI`
- Workflow: `release.yml`
- Environment: `pypi`
- Project: `gnucash-cli`

Release flow:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow will:

1. Run tests.
2. Build wheel and sdist.
3. Create a GitHub Release with generated notes.
4. Publish to PyPI through Trusted Publishing.

Manual workflow dispatch can build the package without publishing by leaving `publish_to_pypi` false.

Do not commit PyPI API tokens. If you choose token-based publishing instead of Trusted Publishing, add the token as a GitHub repository secret named `PYPI_API_TOKEN`; never add it as a public variable.
