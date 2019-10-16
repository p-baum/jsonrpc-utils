# https://www.jsonrpc.org/specification
import json
import uuid
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

JSONRPC_VERSION='2.0'
PARAM_KEY_TYPES = (str, )
PARAM_VALUE_TYPES = PARAM_KEY_TYPES + (int, float)


NO_CODE_ERROR = 'Unknown error'

_ERROR_CODES = {
    -32700: "Parse error", 	# Invalid JSON was received by the server. An error occurred on the server while parsing the JSON text.
    -32600: "Invalid Request",  # The JSON sent is not a valid Request object.
    -32601: "Method not found",  # The method does not exist / is not available.
    -32602: "Invalid params",  # Invalid method parameter(s).
    -32603: "Internal error",  # Internal JSON-RPC error.
    (-32000, -32099): "Server error",  # Reserved for implementation-defined server-errors.
}

_CUSTOM_ERROR_CODES = {}

def register_error(code, message, force=False):
    if not isinstance(code, int):
        raise Exception("error code must be integer")
    try:
        msg, source = get_error(code)
    except KeyError:
        _CUSTOM_ERROR_CODES[code] = message
        return
    if source == 'reserved':
        raise Exception(f"error code {code} is reserved: {_ERROR_CODES[code]}")
    elif code in range(-32768, -32000+1):
        raise ValueError(f"error code {code} is reserved for future use")
    elif source == 'custom' and not force:
        raise Exception(f"error code {code} is already defined: {_CUSTOM_ERROR_CODES[code]}")
    _CUSTOM_ERROR_CODES[code] = message

def get_error(code, default=None):
    if not isinstance(code, int):
        raise Exception("error code must be integer")
    for source, errors in {'custom': _CUSTOM_ERROR_CODES, 'reserved': _ERROR_CODES}.items():
        try:
            return errors[code], source
        except KeyError:
            pass
        for _code, _msg in {c:m for c,m in errors.items() if isinstance(c, tuple)}.items():
            lower, upper = _code
            if code in range(lower, upper+1):
                return _msg, source
    if not default:
        raise KeyError(f"error code {code} does not exist")
    return default, None




class JSONCallError(Exception):

    def __init__(self, code, *args, data=None, _id=None, message=None, **kwargs):
        try:
            if isinstance(code, (str, int)):
                self.code = int(code)
            else:
                raise Exception()
        except Exception:
            if code:
                raise Exception("error code must be integer or none/null")
            self.code = None
            self.message = message or NO_CODE_ERROR
        else:
            # self.code is int
            try:
                self.message, source = get_error(self.code)
                if message and message != self.message:
                    raise Exception(f"inconsistant message for {source} error code {self.code}")
            except KeyError:
                if message:
                    register_error(self.code, message)
                    self.message = message
                else:
                    raise Exception(f"no message available for error code {self.code}")


        self.error_data = data
        self._id = _id if _id is not False else None
        super().__init__(*args, **kwargs)

    @property
    def data(self):
        d = {
            'code': self.code,
            'message': self.message
        }
        if self.error_data:
            d['data'] = self.error_data
        return d

    def response(self, encoding='utf8', **kwargs):
        r = json.dumps(
            {
                'jsonrpc': JSONRPC_VERSION,
                'error': self.data,
                'id': self._id
            },
            ensure_ascii=kwargs.pop('ensure_ascii',False),
            **kwargs
        )
        if encoding:
            return r.encode(encoding)
        return r

    def __str__(self):
        return f"{self.message} [code {self.code}]"

    def __eq__(self, other):
        fields = ['code', 'message', 'error_data']
        if not all(
                this==that for this,that in zip(
                    [getattr(self, f) for f in fields],
                    [getattr(other, f) for f in fields]
                )
            ):
            logger.debug("error fail: props")
            return False
        if self.response() != other.response():
            logger.debug("error fail: response()")
            return False
        return True


class JSONCall:
    FIELDS = [
        'jsonrpc',
        'method',
        'params',
        'id'
    ]

    def __init__(self, method, jsonrpc=None, params=None, _id=True, clean=True):
        # id None==null False==not there
        self.jsonrpc = jsonrpc or JSONRPC_VERSION
        self.method = method
        self.params = params
        self._id = _id
        self.kwargs = {}
        self.args = []
        self._result = None
        self._error = None
        self.success = None
        self._clean()
        
    @property
    def result(self):
        if self.success is None:
            raise Exception("no result or error has been set")
        elif self.success is True:
            return self._result
        elif self.success is False:
            raise self._error
        raise Exception("internal error")

    @property
    def error(self):
        if self.success is None:
            raise Exception("no result or error has been set")
        elif self.success is False:
            return self._error.data
        elif self.success is True:
            return None
        raise Exception("internal error")

    def _clean_id(self, _id):
        try:
            if float(_id).is_integer():
                return _id
        except Exception:
            return _id
        raise JSONCallError(-32600, _id=_id)

    def _clean_params(self, params):
        try:
            params = dict(params)
            if not all(isinstance(k, PARAM_KEY_TYPES) and isinstance(v, PARAM_VALUE_TYPES) for k,v in params.items()):
                raise JSONCallError(-32602, _id=self._id)
            return params
        except (ValueError, TypeError):
            if not isinstance(params, str):
                params = list(params)
            else:
                raise JSONCallError(-32602, _id=self._id)
            if not all(isinstance(v, PARAM_VALUE_TYPES) for v in params):
                raise JSONCallError(-32602, _id=self._id)
            return params 

    def _clean(self, ):
        #if :
        #    if self._id:
        #        raise JSONCallError(-32603, _id=self._id)
        if not self.is_notification:
            if self._id is True:
                self._id = str(uuid.uuid4()).replace('-','')
            elif self._id:
                self._id = self._clean_id(self._id)
            # else id now false or none
        if self.jsonrpc != JSONRPC_VERSION:
            raise JSONCallError(-32600, _id=self._id)
        if not self.method:
            raise JSONCallError(-32600, _id=self._id)
        elif not isinstance(self.method, str):
            raise JSONCallError(-32600, _id=self._id)
        elif self.method.startswith('rpc.'):
            raise JSONCallError(-32600, _id=self._id)
        self.method = str(self.method)
        if self.params:
            self.params = self._clean_params(self.params)
            if isinstance(self.params, list):
                self.args = self.params
            else:
                self.kwargs = self.params

    @classmethod
    def from_request(cls, json_req):
        try:
            d = json.loads(json_req)
        except Exception:
            raise JSONCallError(-32700)
        if isinstance(d, list):
            raise NotImplementedError("batch calls not implemented")
        # filter
        d = {k:v for k,v in d.items() if k in cls.FIELDS}
        # fix id field name clash
        #if :
        d['_id'] = d.pop('id') if 'id' in d else False
            #not bool(len(str(d['_id'])))
            #notification = False
        #else:
        #    d['_id'] = False
            #notification = True
        return cls(d.pop('method', None), **d)

    @classmethod
    def from_url(cls, url):
        url_parts = urlparse(url)
        # use only last value for key in query string
        d = {
            k:v[-1] for k,v in parse_qs(url_parts.query).items()
        }
        if 'method' not in d:
            d['method'] = url_parts.path
        return cls.from_request(json.dumps(d, ensure_ascii=False))

    def set_result(self, result):
        if self.is_notification:
            raise Exception("cannot set result on a notification")
        self._result = result
        self._error = None
        self.success = True

    def set_error(self, code, message=None, data=None):
        if self.is_notification:
            raise Exception("cannot set error on a notification")
        self._error = JSONCallError(code, message=message, data=data)
        self._result = None
        self.success = False

    def response(self, encoding='utf8', **kwargs):
        resp = {'jsonrpc': self.jsonrpc}
        if self.is_notification:
            raise ValueError("notifications have no response")
        elif self.success is None:
            raise ValueError("no result or error has been set")
        elif self.success is True:
            resp['result'] = self._result
        elif self.success is False:
            resp['error'] = self._error.data
        else:
            raise Exception("internal error")
        if self._id is not False:
            resp['id'] = self._id
        r = json.dumps(resp, ensure_ascii=kwargs.pop('ensure_ascii',False), **kwargs)
        if encoding:
            return r.encode(encoding)
        return r

    def assign_response(self, response, **kwargs):
        try:
            r = json.loads(response, **kwargs)
        except Exception:
            self.set_error(-32700)
            raise self._error
        if r['id'] != self._id:
            raise Exception("Response id doesn't match this call.")
        if 'result' in r:
            self.set_result(r['result'])
        elif 'error' in r:
            self.set_error(
                r['error']['code'],
                message=r['error']['message'],
                data=r['error']['data'] if 'data' in r['error'] else None
            )
            raise self._error
        else:
            raise Exception("result or error not provided in response")

    @property
    def is_notification(self):
        return self._id is False

    @property
    def data(self):
        d = {f:getattr(self, f) for f in self.FIELDS if hasattr(self, f) and getattr(self, f) is not None}
        if self._id is not False:
            d['id'] = self._id
        
        return d

    def request(self, encoding='utf8', **kwargs):
        if encoding:
            return str(self).encode(encoding)
        return str(self)

    def __str__(self):
        return json.dumps(self.data, ensure_ascii=False)

    def __eq__(self, other):
        fields = self.FIELDS + ['_id', 'data', 'success', '_error', '_result']
        fields.remove('id')
        if not all(
                this==that for this,that in zip(
                    [getattr(self, k) for k in fields],
                    [getattr(other, k) for k in fields]
                )
            ):
            #print("------------")
            #logger.debug(f"eq fail: props")
            #for k,v in {k:getattr(self, k) for k in fields}.items():
            #    print(f"{k}={v}")
            #error_data = self._error.data if self._error else None
            #print(f'error={error_data}')
            #print("")
            #for k,v in {k:getattr(other, k) for k in fields}.items():
            #    print(f"{k}={v}")
            #error_data = other._error.data if other._error else None
            #print(f'error={error_data}')
            return False
        if self.success is not None and self.response() != other.response():
            logger.debug("eq fail: response")
            return False
        return True
        

