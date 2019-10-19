jsonrpc-utils
=============

Create and send the call on client:
```python
import jsonrpc

client_jsoncall = jsonrpc.JSONCall(method_name, params={'color':'blue', 'size': 4})
returned = my_client_send(client_jsoncall.request())
```

Receive the call on server (responding immediately on error):
```python
import jsonrpc

try:
    server_jsoncall = jsonrpc.JSONCall.from_request(my_server_receive())
except jsonrpc.JSONCallError as jsoncall_error:
    print(f"Error {jsoncall_error.code}: {jsoncall_error.message}")
    my_server_send(jsoncall_error.response())
    return
```  

Server should manage its error codes. For this example we'll assign codes to pythons exceptions:
```python
my_errors = {'Exception': 0}
my_errors.update({
    v.__name__:k for k,v in enumerate(Exception.__subclasses__(), start=1)
})
```

Server calls a method using the request and send it back:
```python
# re-assign method and params for readability
method = server_jsoncall.method
args = server_jsoncall.args
kwargs = server_jsoncall.kwargs
try:
    # try getting a result with your function
    result = getattr(module_or_obj, method)(*args, **kwargs)
except Exception as function_error:
    # set the error
    code = my_errors[function_error.__class__.__name__]
    server_jsoncall.set_error(code, message=str(function_error))
else:
    # or set the result
    server_jsoncall.set_result(result)

# send it back to the client
server_send_func(server_jsoncall.response())
```

Client receives the response. An exception is raised if its an error:
```python
try:
    client_jsoncall.assign_response(returned)
except jsonrpc.JSONCallError as jsoncall_error:
    error = client_jsoncall.error  # or
    error = jsoncall_error.values
else:
    result = client_jsoncall.result
```