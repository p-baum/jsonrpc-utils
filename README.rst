jsonrpc-utils
=============

Bit rough around the edges right now but all tests passing and works well for my needs.

.. code:: python

    import jsonrpc
    json_dumps_kwargs = {'indent': 2}

Create call on client:

.. code:: python

    client_jsoncall = jsonrpc.JSONCall(method_name, params={'color':'blue', 'size': 4})

Send the call:

.. code:: python

    the_call = client_jsoncall.request(encoding='utf8', **json_dumps_kwargs)
    
Receive the call on server (responding immediately if parse error)

.. code:: python

    try:
        server_jsoncall = jsonrpc.JSONCall.from_request(the_call)
    except jsonrpc.JSONCallError as jsoncall_error:
        # parsing error
        error = jsoncall_error.data
        # send the response
        the_response = jsoncall_error.response(encoding='utf8', **json_dumps_kwargs)
        return

Call a method using the request and send it back:

.. code:: python

    method = server_jsoncall.method
    args = server_jsoncall.args
    kwargs = server_jsoncall.kwargs
    try:
        result = getattr(location_of_func, method)(*args, **kwargs)
        server_jsoncall.set_result(result)
    except Exception as e:
        server_jsoncall.set_error(1, message=str(e))
    # send the response
    the_response = server_jsoncall.response() # 'utf8' is default

Client receives the response.
Assigning response raises exception if its an error:

.. code:: python

    try:
        client_jsoncall.assign_response(the_response)
    except jsonrpc.JSONCallError as jsoncall_error:
        error = client_jsoncall.error #or
        error = jsoncall_error.data
    else:
        result = client_jsoncall.result
