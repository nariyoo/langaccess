# -*- coding: utf-8 -*-
"""Lay the release tree over the public repository's working copy, and stop before committing.

The private repository carries the whole construction history and a few files that are not part of
the distribution: the logo-candidate build scripts and their proof sheets. The public repository at
github.com/nariyoo/langaccess carries the release tree and nothing else. This script copies every
file git tracks in the private tree at HEAD, less the exclusions below, into the public working copy,
deletes from the public copy any tracked file the export no longer carries, and prints the public
repository's `git status`. It writes no commit and pushes nothing: both are Nari's, and both are
outward-facing.

    python tools/export_public.py                # report what would change
    python tools/export_public.py --apply        # write the files and print git status

Run from the private repository root, or from a worktree of it with `--public` naming the public
working copy; the default is `../langaccess-public` beside the repository.
"""
import argparse, os, shutil, subprocess, sys, fnmatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.path.normpath(os.path.join(ROOT, '..', 'langaccess-public'))

# Not part of the distribution. Everything else git tracks ships.
EXCLUDE = (
    'figures/build_logo_candidates.py', 'figures/build_logo_g.py', 'figures/build_logo_r2.py',
    'figures/build_wordmark_options.py', 'figures/logo_candidates*.png',
    'figures/wordmark_options.png',
)


def _git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True,
                          encoding='utf-8').stdout


def _excluded(path):
    return any(fnmatch.fnmatch(path, pat) for pat in EXCLUDE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--public', default=PUBLIC, help='the public working copy')
    a = ap.parse_args()
    public_root = os.path.normpath(a.public)
    if not os.path.isdir(os.path.join(public_root, '.git')):
        sys.exit('no public working copy at %s' % public_root)
    private = [p for p in _git(ROOT, 'ls-files').splitlines() if p and not _excluded(p)]
    public = [p for p in _git(public_root, 'ls-files').splitlines() if p]
    assert private, 'the private tree lists no files; run this from the repository root'
    to_delete = sorted(set(public) - set(private))
    changed, added = [], []
    for p in private:
        src, dst = os.path.join(ROOT, p), os.path.join(public_root, p)
        if not os.path.exists(dst):
            added.append(p)
        else:
            with open(src, 'rb') as f1, open(dst, 'rb') as f2:
                if f1.read() != f2.read():
                    changed.append(p)
    print('export from %s' % ROOT)
    print('  %d files tracked, %d excluded by pattern' % (
        len(private), len(_git(ROOT, 'ls-files').splitlines()) - len(private)))
    print('  added %d, changed %d, deleted %d' % (len(added), len(changed), len(to_delete)))
    for label, items in (('added', added), ('changed', changed), ('deleted', to_delete)):
        for p in items:
            print('    %-8s %s' % (label, p))
    if not a.apply:
        print('dry run; add --apply to write')
        return
    for p in added + changed:
        dst = os.path.join(public_root, p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, p), dst)
    for p in to_delete:
        os.remove(os.path.join(public_root, p))
    print(_git(public_root, 'status', '--short'))
    print('written; nothing committed. Review, then commit in %s as Nari Yoo.' % public_root)


if __name__ == '__main__':
    main()
