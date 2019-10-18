jsonrpc-utils
=============

.. code:: python

    import jsonrpc

Create call on client:

.. code:: python

    client_jsoncall = jsonrpc.JSONCall(method_name, params={'color':'blue', 'size': 4})

Send the call:

.. code:: python

    returned = client_send_func(client_jsoncall.request())
    
Receive the call on server (responding immediately on error)

.. code:: python

    the_call = my_server_readline()
    try:
        server_jsoncall = jsonrpc.JSONCall.from_request(the_call)
    except jsonrpc.JSONCallError as jsoncall_error:
        print(f"Error: {jsoncall_error.message}")
        server_send_func(jsoncall_error.response())
        return

Server calls a method using the request and send it back:

.. code:: python

    method = server_jsoncall.method
    args = server_jsoncall.args
    kwargs = server_jsoncall.kwargs
    # set the result (or error)
    try:
        result = getattr(module_or_obj, method)(*args, **kwargs)
        server_jsoncall.set_result(result)
    except Exception as function_error:
        server_jsoncall.set_error(1, message=str(function_error))
    # send the response
    server_send_func(server_jsoncall.response())

Client receives the response.
Assigning response raises exception if its an error:

.. code:: python

    try:
        client_jsoncall.assign_response(returned)
    except jsonrpc.JSONCallError as jsoncall_error:
        error = client_jsoncall.error  # or
        error = jsoncall_error.values
    else:
        result = client_jsoncall.result
