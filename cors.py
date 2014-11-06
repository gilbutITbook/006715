import webob.exc
import webob
from keystone.common import wsgi


"""
Cors Middleware

Middleware that adds Cross Origin Resource Sharing (short: CORS) headers. This
enables client-side javascript applications to manipulate OpenStack rest
services, without hosting the application on the same server as the OpenStack
services.

More information about CORS can be found at: http://www.w3.org/TR/cors/

The best place for this middleware is early in the pipeline.
Configuration details:

[filter:cors]
paste.filter_factory = openstack.common.middleware.cors:filter_factory
## Allowed origins. Either a wildcard, or a space delimited list of domains.
## Note that these domains don't support wildcards of partial matches. This
## list is sent to the browser, and it is enforced by this middleware.
# allow_origins = *
## Methods to allow. A comma separated list of allowed methods.This
## list is sent to the browser, and it is enforced by this middleware.
# allow_methods = GET, POST, PUT, DELETE, OPTIONS
## A comma separated list of headers the client is allowed to customize. This
## is sent to the browser as-is; it is not enforced by this middleware
# allow_headers = Origin, Content-type, Accept, X-Auth-Token
## Whether the browser allows the app developper to send credentials.
# allow_credentials = false
## Whether this middleware responds to pre-flight OPTIONS requests. If you have
## implemented OPTIONS requests somewhere down the pipeline, you should switch
## this off. Even when switched off, the CORS headers are added to the
## response, so the pre-flight request will work as intended, but it may
## trigger unintended side-effects in your implementation.
# hijack_options = true
## The suggested cache time
# max_age = 3600
## What headers to expose to javascript applications. Applications can always
## query the "simple response headers": Cache-control, Content-Language,
## Content-Type, Expires, Last-Modified and Pragma.
## http://www.w3.org/TR/cors/#handling-a-response-to-a-cross-origin-request
## The client application will also gain access to any other headers listed
## here.
# expose_headers = etag, x-timestamp, x-trans-id, vary
"""

DEFAULT_CONFIGURATION = {
    'allow_origins': '*',
    'allow_methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'allow_headers': 'Origin, Content-type, Accept, X-Auth-Token',
    'expose_headers': 'etag, x-timestamp, x-trans-id, vary',
    'allow_credentials':  'false',
    'hijack_options': 'true',
    'max_age': '3600',
}

TRUE_STRINGS = ('1', 't', 'true', 'on', 'y', 'yes')
FALSE_STRINGS = ('0', 'f', 'false', 'off', 'n', 'no')

def bool_from_string(subject, strict=False):
    """Interpret a string as a boolean.

    A case-insensitive match is performed such that strings matching 't',
    'true', 'on', 'y', 'yes', or '1' are considered True and, when
    `strict=False`, anything else is considered False.

    Useful for JSON-decoded stuff and config file parsing.

    If `strict=True`, unrecognized values, including None, will raise a
    ValueError which is useful when parsing values passed in from an API call.
    Strings yielding False are 'f', 'false', 'off', 'n', 'no', or '0'.
    """
    if not isinstance(subject, basestring):
        subject = str(subject)

    lowered = subject.strip().lower()

    if lowered in TRUE_STRINGS:
        return True
    elif lowered in FALSE_STRINGS:
        return False
    elif strict:
        acceptable = ', '.join(
            "'%s'" % s for s in sorted(TRUE_STRINGS + FALSE_STRINGS))
        msg = _("Unrecognized value '%(val)s', acceptable values are:"
                " %(acceptable)s") % {'val': subject,
                                      'acceptable': acceptable}
        raise ValueError(msg)
    else:
        return False

class CorsMiddleware(wsgi.Middleware):

    def __init__(self, *args, **kwargs):
        conf = DEFAULT_CONFIGURATION.copy()
        conf.update(kwargs)
        self.allowed_origins = set(conf['allow_origins'].split())
        self.allowed_methods = set(method.strip().upper() for method in
                                   conf['allow_methods'].split(','))
        self.hijack_options = bool_from_string(conf['hijack_options'])

        headers = {}
        headers['access-control-allow-origin'] = ' '.join(self.allowed_origins)
        headers['access-control-max-age'] = conf['max_age']
        headers['access-control-allow-methods'] = conf['allow_methods']
        headers['access-control-allow-headers'] = conf['allow_headers']
        headers['access-control-expose-headers'] = conf['expose_headers']
        headers['access-control-allow-credentials'] = conf['allow_credentials']
        self.cors_headers = headers

        super(CorsMiddleware, self).__init__(*args)

    def process_request(self, request):
        """
        Enforce the allow_origin option, and optionally hijack OPTIONS reqs.
        """
        origin = request.headers.get('Origin')
        if origin:
            if origin not in self.allowed_origins and \
                  '*' not in self.allowed_origins:
                return webob.exc.HTTPUnauthorized()

            if request.method not in self.allowed_methods:
                return webob.exc.HTTPUnauthorized()

            if self.hijack_options and request.method == 'OPTIONS':
                # Process the preflight response, by just sending an empty '200 OK'.
                return self.process_response(request, webob.Response())

    def process_response(self, request, response):
        # if the original request isn't known, just assume this was a
        # CORS-enabled request.
        if not response.request or 'Origin' in response.request.headers:
            # add the necessary headers to the response.
            response.headers.update(self.cors_headers)
        return response

