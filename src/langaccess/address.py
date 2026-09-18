# -*- coding: utf-8 -*-
"""Whether a string is an address this package can read, decided before a browser is started.

This is the one check that has to happen first, and the reason is not efficiency. Everything
downstream of it answers with a Result, and a Result carries a verdict; so a string that was never
an address, handed to the audit, comes back as a site that could not be reached. In a study those
rows are counted as sites that refused the crawler when the truth is that nobody ever typed a site.
`htp://example.org` is the shape that matters: it is a typo a person will not notice in a
thousand-row file, and the tool used to answer it with `unreachable` and no hint that the address
was the problem.

A string is auditable when, after the normalisation this package has always applied, it parses to an
http or https URL whose host carries at least one dot or is `localhost`, holds no whitespace
anywhere, names no user and no password before the host, and does not open with a scheme of any
other kind. Everything else is a REJECTED INPUT, which is not a reading: it produces no verdict, no
JSON line and no stored row, and it is named on stderr with the reason.

`mailto:a@b.c` is the second shape that matters, and it was accepted until 0.2.0. It carries no
`//`, so the normalisation put `https://` in front of it, and `urlsplit` read the result as a URL
whose userinfo is `mailto:a` and whose host is `b.c`: an email address in a column of websites came
back a site, and whatever the audit made of `b.c` was recorded against the organization. A scheme
token followed by a colon and something that is not a port number is now refused, which answers
`tel:`, `sms:`, `javascript:`, `data:`, `file:`, `ftp:` and `about:` in the same rule, and userinfo
is refused on its own account, since no public website address carries credentials.

The rule is deliberately syntactic. Nothing here resolves a name or opens a socket, so the answer is
the same on a machine with no network as on one with, and a run over a thousand addresses does not
pay a DNS lookup per address to find out that four of them were words. Whether a host exists, and
whether it sits on the public internet, are separate questions asked later and by other code:
`--block-private-hosts` in the audit, and `public_http_url` in the web front end, which layers its
DNS test on top of this function so that the two front doors agree about what an address is.
"""
import re
from urllib.parse import urlsplit

# Anything of the form scheme:// at the front, whatever the scheme. Only a string with no scheme at
# all is given one. Prepending https:// to whatever was typed turned `htp://example.org` into
# `https://htp://example.org`, whose scheme is https, so the scheme test below never saw the typo
# it exists to catch.
_SCHEME = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://')

# A scheme token, a colon, and something that is neither `//` nor a port number. `mailto:a@b.c` is
# the shape this catches and the reason the rule exists: it carries no `//`, so the normalisation
# below prepended `https://`, and `urlsplit` then read `mailto:a` as userinfo and `b.c` as the host,
# so an email address came back an auditable website. The same normalisation admitted `tel:`,
# `javascript:`, `data:` and the rest of them.
#
# The one string of this shape that IS an address is a host and a port, `localhost:8000` or
# `example.org:8080/x`, so the group after the colon is read up to the first `/`, `?` or `#` and the
# address is kept when that group is a run of digits. A host whose first character is a digit
# (`93.184.216.34:8080`) never reaches this test, because a scheme cannot start with one.
_SCHEMELESS_COLON = re.compile(r'^([a-zA-Z][a-zA-Z0-9+.-]*):(?!//)([^/?#]*)')
_PORT = re.compile(r'^[0-9]+$')

# Named so the message can say which scheme was typed. The general rule above covers these and
# every other scheme nobody has thought of; the list exists because `mailto:` and `tel:` are what
# actually turn up in a column of websites copied out of a directory, and a person reading
# `its scheme is 'mailto'` acts on it faster than a person reading a sentence about colons.
_NON_WEB_SCHEME = frozenset((
    'mailto', 'tel', 'sms', 'javascript', 'data', 'file', 'ftp', 'about',
))

# The one host with no dot in it that names something real. A bare word is otherwise a search term,
# a machine name on somebody's own network, or a typo, and none of the three is a site this package
# can make a statement about.
_DOTLESS_HOST = 'localhost'


class AddressRejected(ValueError):
    """A string that is not an address, carrying the string and why it is not one.

    Both halves matter to a caller. The reason is what a person acts on, and the raw string is what
    they search their input file for, which is the whole difficulty of a rejected row in a run over
    a thousand of them.
    """

    def __init__(self, raw, reason):
        self.raw = raw
        self.reason = reason
        super().__init__('%r is not a web address: %s' % (raw, reason))


def auditable_url(raw, ports=None):
    """Return the normalised address, or raise `AddressRejected` naming what is wrong with it.

    `ports` limits which port numbers are allowed, as the web front end does with (80, 443). The
    default of None allows any, because the command line accepts `localhost` and a site served on a
    development machine is rarely on port 80.

    The returned string is the normalised form, which is what the web endpoint fetches. The command
    line passes the string the user typed to the audit instead, unchanged, so that the `url`
    field of every result stays the address the run was given.
    """
    u = (raw or '')
    if not u.strip():
        raise AddressRejected(raw, 'it is empty')
    u = u.strip()
    # Before anything else, because it is the shape a search phrase has and the message for it
    # should not be about schemes or hosts. A search phrase reached the browser with https:// on
    # the front of it and came back as a site that could not be read.
    if any(ch.isspace() for ch in u):
        raise AddressRejected(raw, 'it holds a space, and no web address does')
    if not _SCHEME.match(u):
        m = _SCHEMELESS_COLON.match(u)
        if m and not _PORT.match(m.group(2)):
            token = m.group(1).lower()
            if token in _NON_WEB_SCHEME:
                raise AddressRejected(
                    raw, 'its scheme is %r, and only http and https can be read. That is an '
                         'address of another kind, not a website' % token)
            raise AddressRejected(
                raw, 'it opens with %r and a colon, which is a scheme and not a host, and what '
                     'follows the colon is not a port number' % m.group(1))
        u = 'https://' + u
    try:
        p = urlsplit(u)
        host, port = p.hostname, p.port
    except ValueError as e:
        # A bracket that opens an IPv6 address and never closes it, or a port that is not a number.
        # Both used to come out of urlsplit as an exception nobody caught.
        raise AddressRejected(raw, 'it cannot be read as a URL (%s)' % e)
    if p.scheme not in ('http', 'https'):
        raise AddressRejected(
            raw, 'its scheme is %r, and only http and https can be read. A scheme a letter out of '
                 'true is the usual cause' % p.scheme)
    if not host:
        raise AddressRejected(raw, 'there is no host in it')
    # No public website address carries credentials, and this is also the second half of the
    # `mailto:` defect: `https://mailto:a@b.c` is a URL whose userinfo is `mailto:a`, so anything
    # of that shape has to be refused whether the string arrived with its own scheme or not.
    if p.username is not None or p.password is not None:
        raise AddressRejected(
            raw, 'it carries a user name or a password before the host, and no public website '
                 'address does')
    if '.' not in host and host != _DOTLESS_HOST:
        raise AddressRejected(
            raw, 'its host %r holds no dot, so it names no site on the internet' % host)
    if ports is not None and port is not None and port not in ports:
        raise AddressRejected(
            raw, 'it names port %d, and only %s can be read'
                 % (port, ' and '.join(str(n) for n in ports)))
    return u
