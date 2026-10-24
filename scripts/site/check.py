"""Check the assembled public site for missing files, anchors and private paths."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote, urlsplit

BLOCKED = {'.env', '.git', '.aws', '.codex', '.agents', 'node_modules', 'm0', 'reviews', 'submissions', '__pycache__'}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.links, self.assets = set(), [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag in {'script', 'img', 'source'} and attrs.get('src'):
            self.assets.append(attrs['src'])
        if tag == 'link' and attrs.get('href'):
            self.assets.append(attrs['href'])


def check(root):
    root = root.absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('site root must be a regular directory')
    errors, pages = [], {}
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if (path.is_symlink() or any(p.lower() in BLOCKED or p.lower().startswith('.env')
                or (p.startswith('.') and relative.as_posix() != '.hindsight-site-build')
                or p.lower() in {'credentials.txt', 'credentials.json', 'secrets.txt', 'secrets.json', 'id_rsa', 'id_ed25519'}
                for p in relative.parts)):
            errors.append('disallowed public path: ' + relative.as_posix())
            continue
        if path.is_file() and path.suffix not in {'.html', '.css', '.js', '.json', '.svg', '.woff2', '.txt'} and relative.as_posix() != '.hindsight-site-build':
            errors.append('unexpected public file: ' + relative.as_posix())
        if path.is_file() and path.suffix == '.html':
            page = Page()
            page.feed(path.read_text())
            pages[relative.as_posix()] = page
    for required in ('index.html', 'docs/index.html', 'docs/getting-started.html', 'docs/remediation.html', 'docs/report-format.html', 'assets/fonts/OFL.txt'):
        if not (root / required).is_file():
            errors.append('missing required page/asset: ' + required)

    def target(source, href, asset=False):
        url = urlsplit(href)
        if url.scheme or url.netloc:
            if asset and url.scheme != 'data':
                errors.append('external subresource: ' + source)
            return
        path = unquote(url.path)
        name = posixpath.normpath(path.lstrip('/') if path.startswith('/') else posixpath.join(posixpath.dirname(source), path)) if path else source
        if name == '..' or name.startswith('../'):
            errors.append('path escapes site: ' + source)
            return
        resolved = root / name
        if resolved.is_dir():
            name = posixpath.join(name, 'index.html')
        elif not resolved.is_file() and not Path(name).suffix:
            name += '.html'
        if not (root / name).is_file():
            errors.append('missing link/asset: ' + source + ' -> ' + href)
        elif not asset and url.fragment and name in pages and unquote(url.fragment) not in pages[name].ids:
            errors.append('missing anchor: ' + source + ' -> ' + href)
    for name, page in pages.items():
        for href in page.links:
            target(name, href)
        for href in page.assets:
            target(name, href, True)
    for path in root.rglob('*.css'):
        if path.is_symlink():
            continue
        for href in re.findall(r'url\(\s*[\'"]?([^\'"\)\s]+)', path.read_text()):
            target(path.relative_to(root).as_posix(), href, True)
    return errors, len(pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('site-dist'))
    args = parser.parse_args()
    try:
        errors, count = check(args.root)
        if errors:
            for error in errors[:30]:
                print(error)
            return 1
        print(f'Public site checks passed: {count} pages; local links/assets resolve and private paths are excluded.')
        return 0
    except (OSError, ValueError):
        print('Public site check failed: invalid or unreadable build output.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
