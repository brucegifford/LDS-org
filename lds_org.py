import os
import contextlib
import requests

CONFIG_URL = "https://tech.lds.org/mobile/ldstools/config.json"
ENV_USERNAME = 'LDSORG_USERNAME'
ENV_PASSWORD = 'LDSORG_PASSWORD'

__version__ = open(os.path.join(os.path.dirname(__file__), 'VERSION')).read().strip()


@contextlib.contextmanager
def session(username=None, password=None):
    """A context manager.

    Example:
    ```
    with session() as lds:
        rv = lds.get(....)
    ```
    """
    lds = LDSOrg(username, password, signin=True)
    yield lds
    lds.get(lds['signout-url'])


class LDSOrg(object):

    """Access LDS.org JSON web tools.

    Access LDS.org and the lds tools in JSON.  You can also use the session
    to access webpages and screen scrape from there.
    """

    def __init__(self, username=None, password=None, signin=False,
                 url='https://ident.lds.org/sso/UI/Login'):
        """Get endpoints and possibly signin.

        :param username: LDS.org username
        :param password: LDS.org password
        :param signin: Sign in using environment variables when not
                     supplying the username and password
        :param url: override the current signin URL when it changes
        """
        self.session = requests.Session()
        self.unitNo = ''
        self._get_endpoints()
        if username or signin:
            self.signin(username, password, url)

    def __iter__(self):
        """Iterate through the endpoints.  """
        return iter(self.endpoints)

    def __getitem__(self, key):
        """Simplify endpoint usage.  """
        return self.endpoints[key]

    def __getattr__(self, key):
        """Reflect to session for any needs.

        Now we can use the class instance just as we would a session.
        """
        return getattr(self.session, key)

    def signin(self, username=None, password=None,
               url='https://ident.lds.org/sso/UI/Login'):
        """Sign in to LDS.org using a member username and password.

        :param username: LDS.org username
        :param password: LDS.org password

        To keep these values out of code, you can use the following
        environment variables: LDSORG_USERNAME AND LDSORG_PASSWORD
        """
        if username is None:
            username = os.getenv(ENV_USERNAME)
        if password is None:
            password = os.getenv(ENV_PASSWORD)

        rv = self.session.post(self.endpoints['auth-url'],
                               data={'username': username,
                                     'password': password})
        if 'etag' not in rv.headers:
            raise ValueError('Username/password failed')

        # Get the persons unit number, needed for other endponts
        r = self.get('current-user-unit')
        assert r.status_code == 200
        self.unitNo = r.json()['message']

    def get(self, url, *args, **kwargs):
        """Get an HTTP response from endpoint or URL.

        Some endpoints need substitution to create a valid URL. Usually,
        this appears as %@ in the endpoint.  By default this method will
        replace all occurances of %@ in the endpoint with the ward number
        of the logged in user.  You can use the ward_No parameter or fix
        it yourself if this is not the correct behaviour.

        :param url: an endpoint or URL
        :param args: substituation for %* in the endpoint
        :param ward_No: for use with an endpoint
        :param kwargs: paramaters for :meth:`requests.Session.get`
        """
        try:
            url = self.endpoints[url]
        except KeyError:
            pass
        else:
            # Fix any substitution as needed
            url = url.replace('%@', kwargs.pop('ward_No', self.unitNo))
            if '%' in url:
                if args:
                    url = url % args
                else:
                    raise ValueError("endpoint {} needs arguments".format(url))
        return self.session.get(url, **kwargs)

    def _get_endpoints(self):
        """Get the currently supported endpoints provided by LDS Tools.

        See https://tech.lds.org/wiki/LDS_Tools_Web_Services
        """
        # Get the endpoints
        rv = self.session.get(CONFIG_URL)
        assert rv.status_code == 200
        self.endpoints = rv.json()


if __name__ == "__main__":  # pragma: no cover
    import sys
    import argparse
    import getpass
    import pprint

    parser = argparse.ArgumentParser()
    parser.add_argument('-e', metavar='ENDPOINT', help="Endpoint to pretty print")
    parser.add_argument('arg', nargs='*', help='Arguments for endpoint URLs')
    parser.add_argument('--ask', action='store_true',
                        help='ask for username/password')

    args = parser.parse_args()
    if args.ask:
        username = raw_input('LDS.org username:')
        password = getpass.getpass('LDS.org password:')
    else:
        username = os.getenv(ENV_USERNAME)
        password = os.getenv(ENV_PASSWORD)

    lds = LDSOrg()

    if not args.e:
        print(sorted(str(k) for k, v in lds.endpoints.items()
                     if isinstance(v, basestring) and v.startswith('http')))
    else:
        if not (username and password):
            print("Either use --ask or set environment {0} and {1}"
                  .format(ENV_USERNAME, ENV_PASSWORD))
            sys.exit(1)
        lds.signin(username, password)
        rv = lds.get(args.e, *[int(_) for _ in args.arg])
        content_type = rv.headers['content-type']
        if 'html' in content_type:
            print(rv.url)
            print(rv.text.encode('utf-8'))
        elif 'json' in content_type:
            pprint.pprint(rv.json())
        if rv.status_code != 200:
            print("Error: %d" % rv.status_code)