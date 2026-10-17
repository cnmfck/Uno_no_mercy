# Building and Publishing Releases

## GitHub Build: All Four Platforms

1. Upload this project's contents to the repository root. The `main.py` file and `.github` directory must be at the root, with the workflow at `.github/workflows/build-release.yml`.
2. Open the repository's **Actions** tab and select **Build desktop releases**.
3. Click **Run workflow** to build all four platforms without publishing a release. The workflow must be on the repository's default branch for this button to appear.
4. After a successful run, download each `release-*` artifact. Extract the outer artifact ZIP to obtain the actual platform archive and its checksum file.

The workflow builds Windows x64, Intel macOS, Apple Silicon macOS, and Linux x64. Each runner executes the test suite, builds with PyInstaller, and opens/closes the packaged application as a startup check before archiving it.

## Publish a GitHub Release

After uploading the workflow and confirming the build:

1. Open **Releases** and select **Draft a new release**.
2. Create the tag `v6.0.0` on the commit containing these files.
3. Use `UNO No Mercy v6.0.0` as the title and paste the contents of `RELEASE_NOTES.md` as the description.
4. Select **Publish release**. This triggers the four builds.
5. After every build succeeds, the workflow attaches all four native archives and their checksum files to that release.

Publishing displays the release before the builds finish. For a release that has assets immediately, run the manual workflow first and attach its downloaded files while drafting the release. The published-release workflow will rebuild and replace files with the same names.

For subsequent releases, use a tag such as `v6.0.1` and update the release notes. Tags must match `vMAJOR.MINOR.PATCH`, optionally followed by a prerelease suffix such as `-beta.1`.

## Build Locally

Run these commands from the project root with Python 3.10+ and working Tkinter:

```bash
python -m pip install -r requirements-build.txt
python scripts/build_release.py --version v6.0.0
```

Use `python3` where appropriate. Build separately on each target OS and CPU architecture. Files appear in `release-assets/`; intermediate files are written to `build/` and `dist/`.

On a Linux machine without a display, use Xvfb to run the normal graphical check, or explicitly pass `--headless` to perform only imports, Tcl initialization, and engine checks. The latter records `graphical: false` in `BUILD_CHECK.json`.

Windows packages contain an executable plus its required `_internal` folder. macOS bundles are archived with `ditto` to preserve their framework layout. Linux packages use tar to preserve permissions and symbolic links.

## Verification Status

The release configuration was prepared locally. The four-platform GitHub workflow still needs to run in your repository. A local Linux x64 binary was built separately and checked without a graphical display; it carries an explicit glibc 2.39/headless-check filename label.

## References

- [PyInstaller operating model](https://pyinstaller.org/en/stable/operating-mode.html)
- [GitHub-hosted runner platforms](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub CLI release asset upload](https://cli.github.com/manual/gh_release_upload)
