import unittest
import json
import logging

from jsonrpc import __version__
from jsonrpc import jsonrpc


def test_version():
    assert __version__ == '0.1.1'
    
logging.basicConfig(format="%(module)s: %(levelname)s: %(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestJSONRPC(unittest.TestCase):
    def create(self, call, notification=False):
        call_d = json.loads(call)
        client_jsoncall = jsonrpc.JSONCall(
            call_d['method'],
            **{k:v for k,v in call_d.items() if k not in ['method','id']},
            _id=call_d.get('id',False)
        )
        server_jsoncall = jsonrpc.JSONCall.from_request(client_jsoncall.request())
        self.assertEqual(client_jsoncall, server_jsoncall)
        self.assertEqual(client_jsoncall.values, call_d)
        self.assertEqual(client_jsoncall.request(encode='utf8'), call.encode('utf8'))
        return client_jsoncall

    def test_eq_method(self):
        r1 = '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": "23"}'
        r2 = '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": "24"}'
        a = self.create(r1)
        b = self.create(r1)
        self.assertEqual(a,b)
        b = self.create(r2)
        self.assertNotEqual(a,b)
        # after setting result
        a.set_result("yes")
        b = self.create(r1)
        self.assertNotEqual(a,b)
        b.assign_response('{"jsonrpc": "2.0", "result": "yes", "id": "23"}')
        self.assertEqual(a,b)
        # after setting error
        error_resp = '{"jsonrpc": "2.0", "error": {"code": 5, "message": "Oh no!"}, "id": "23"}'
        a.set_error(5, message="Oh no!")
        self.assertEqual(error_resp, a.response(encoding=None))
        b = self.create(r1)
        self.assertNotEqual(a,b)
        with self.assertRaises(jsonrpc.JSONCallError):
            b.assign_response(error_resp)
        self.assertEqual(a,b)
        with self.assertRaises(jsonrpc.JSONCallError):
            b.assign_response(a.response())
        self.assertEqual(a,b)

    # An identifier established by the Client that MUST contain a String, Number,
    # or NULL value if included. If it is not included it is assumed to be a
    # notification.
    def test_id_ok(self):
        self.create(
            '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": 23}'
        )
        self.create(
            '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": "23"}'
        )
        self.create(
            '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": "we.!3§"}'
        )
        self.create(
            '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": null}'
        )

    def test_id_fails(self):
        call = '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": "1.2"}'
        with self.assertRaises(jsonrpc.JSONCallError) as e:
            self.create(call)
        self.assertIn('-32600',str(e.exception))
        call = '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": 2.3}'
        with self.assertRaises(jsonrpc.JSONCallError) as e:
            self.create(call)
        self.assertIn('-32600',str(e.exception))

    def test_set_server_errors(self):
        # -32000 to -32099 Reserved for implementation-defined server-errors.
        # (better read as -32099 to -32000)

        # test type enforcement
        server_errors = {
            '23': 'not an int'
        }
        with self.assertRaises(TypeError): 
            jsonrpc.set_server_errors(server_errors)
        server_errors = {
            23: 122
        }
        with self.assertRaises(TypeError): 
            jsonrpc.set_server_errors(server_errors)

        # test range enforcement
        server_errors = {
            -32100: 'something weird'
        }
        with self.assertRaises(ValueError): 
            jsonrpc.set_server_errors(server_errors)
        server_errors = {
            -32099: 'something weird'
        }
        jsonrpc.set_server_errors(server_errors)
        server_errors = {
            -32000: 'something weird'
        }
        jsonrpc.set_server_errors(server_errors)
        server_errors = {
            -31999: 'something weird'
        }
        with self.assertRaises(ValueError): 
            jsonrpc.set_server_errors(server_errors)
    
    def test_error_codes(self):
        client_jsoncall = self.create(
            '{"jsonrpc": "2.0", "method": "add", "params": [1], "id": 1}',
        )
        server_jsoncall = jsonrpc.JSONCall.from_request(client_jsoncall.request()) 
        with self.assertRaises(ValueError): 
            server_jsoncall.set_error(1)
        server_jsoncall.set_error(1, message="A small mistake")
        self.assertEqual(server_jsoncall.error['message'], "A small mistake")
        with self.assertRaises(jsonrpc.JSONCallError) as e: 
            client_jsoncall.assign_response(server_jsoncall.response())
        self.assertEqual(client_jsoncall, server_jsoncall)
        self.assertEqual(client_jsoncall.error, e.exception.values)

        # try to use builtin code with wrong message
        with self.assertRaises(ValueError) as e: 
            server_jsoncall.set_error(-32700, message="A big mistake")
        self.assertIn('Parse error', str(e.exception))

        # try to use server-error code with wrong message
        server_errors = {
            -32000: 'something weird'
        }
        jsonrpc.set_server_errors(server_errors)
        with self.assertRaises(ValueError) as e: 
            server_jsoncall.set_error(-32000, message="A big mistake")
        self.assertIn('something weird', str(e.exception))

    def compare_example(self, call, expected_response, result=None, error_code=None):
        # create the call
        client_jsoncall = self.create(call)
        # send the call
        the_call = client_jsoncall.request()
        # check the call is serialized
        self.assertIsInstance(the_call, bytes)
        # receive the call
        server_jsoncall = jsonrpc.JSONCall.from_request(the_call)
        # check server and client have the same call
        self.assertEqual(
            server_jsoncall,
            client_jsoncall
        )
        # server adds result or error
        if result:
            server_jsoncall.set_result(result)
        elif error_code:
            server_jsoncall.set_error(code=error_code)
        # compare server result to whats expected (data)
        self.assertEqual(
            json.loads(server_jsoncall.response()),
            json.loads(expected_response)
        )
        # compare server result to whats expected (serialized)
        self.assertEqual(
            server_jsoncall.response(encoding='utf8'),
            expected_response.encode('utf8')
        )
        # send the response back to the client
        the_response = server_jsoncall.response()
        # check the_response is serialized
        self.assertIsInstance(the_response, bytes)
        # receive the response
        if error_code:
            # assigning response raises exception if its an error
            with self.assertRaises(jsonrpc.JSONCallError) as e:
                client_jsoncall.assign_response(the_response)
            # client and server should now have same error data
            self.assertIsInstance(client_jsoncall.error, dict)
            self.assertEqual(client_jsoncall.error, server_jsoncall.error)
            # error is also available on exception
            self.assertEqual(client_jsoncall.error, e.exception.values)
        else: # result
            client_jsoncall.assign_response(the_response)
            # client and server should now have same result
            self.assertEqual(client_jsoncall.result, server_jsoncall.result)

    def notification(self, call):
        jsoncall = self.create(
            call,
            notification=True
        )
        self.assertEqual(jsoncall._id, False)
        self.assertTrue(jsoncall.is_notification)
        with self.assertRaises(Exception) as e:
            jsoncall.set_result("69")
        self.assertEqual(str(e.exception), 'cannot set result on a notification')
        with self.assertRaises(Exception) as e:
            jsoncall.set_error(code=1)
        self.assertEqual(str(e.exception), 'cannot set error on a notification')

    # examples from https://www.jsonrpc.org/specification#examples
    def test_examples(self):
        # rpc call with positional parameters:
        self.compare_example(
            '{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}',
            '{"jsonrpc": "2.0", "result": 19, "id": 1}',
            result=19
        )
        self.compare_example(
            '{"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": 2}',
            '{"jsonrpc": "2.0", "result": -19, "id": 2}',
            result=-19
        )
        # rpc call with named parameters:
        self.compare_example(
            '{"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}',
            '{"jsonrpc": "2.0", "result": 19, "id": 3}',
            result=19
        )
        self.compare_example(
            '{"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 42, "subtrahend": 23}, "id": 4}',
            '{"jsonrpc": "2.0", "result": 19, "id": 4}',
            result=19
        )
        # a Notification:
        self.notification('{"jsonrpc": "2.0", "method": "update", "params": [1, 2, 3, 4, 5]}')
        self.notification('{"jsonrpc": "2.0", "method": "foobar"}')

        # rpc call of non-existent method:
        self.compare_example(
            '{"jsonrpc": "2.0", "method": "foobar", "id": "1"}',
            '{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "1"}',
            error_code=-32601
        )
        # rpc call with invalid JSON:
        with self.assertRaises(jsonrpc.JSONCallError) as e:
            jsonrpc.JSONCall.from_request(
                '{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]'
            )
        self.assertEqual(
            json.loads(e.exception.response()),
            json.loads('{"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}')
        )
        self.assertEqual(
            e.exception.response(encoding='utf8'),
            '{"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}'.encode('utf8')
        )

        # rpc call with invalid Request object:
        with self.assertRaises(jsonrpc.JSONCallError) as e:
            jsonrpc.JSONCall.from_request(
                '{"jsonrpc": "2.0", "method": 1, "params": "bar"}'
            )
        self.assertEqual(
            e.exception.response(encoding='utf8'),
            '{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}'.encode('utf8')
        )
    
# batch not implemented
"""

rpc call Batch, invalid JSON:

--> [
{"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
{"jsonrpc": "2.0", "method"
]
<-- {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": null}

rpc call with an empty Array:

--> []
<-- {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}

rpc call with an invalid Batch (but not empty):

--> [1]
<-- [
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
]

rpc call with invalid Batch:

--> [1,2,3]
<-- [
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
{"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null}
]

rpc call Batch:

--> [
        {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
        {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
        {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
        {"foo": "boo"},
        {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
        {"jsonrpc": "2.0", "method": "get_data", "id": "9"} 
    ]
<-- [
        {"jsonrpc": "2.0", "result": 7, "id": "1"},
        {"jsonrpc": "2.0", "result": 19, "id": "2"},
        {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": null},
        {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": "5"},
        {"jsonrpc": "2.0", "result": ["hello", 5], "id": "9"}
    ]

rpc call Batch (all notifications):

--> [
        {"jsonrpc": "2.0", "method": "notify_sum", "params": [1,2,4]},
        {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]}
    ]
<-- //Nothing is returned for all notification batches
"""
