jsonrpc-utils
=============

::
    import jsonrpc

Create call on client::
    client_jsoncall = jsonrpc.JSONCall(call)
Send the call::
    the_call = client_jsoncall.request()

Receive the call on server::
    server_jsoncall = jsonrpc.JSONCall.from_request(the_call)

Server adds result::
    server_jsoncall.set_result(result)
or perhaps an error::
    server_jsoncall.set_error(code=error_code)


Send the response back to the client::
    the_response = server_jsoncall.response()

Client receives the response.
Assigning response raises exception if its an error::
    try:
        client_jsoncall.assign_response(the_response)
    except jsonrpc.JSONCallError:
        error = client_jsoncall.error
    else:
        result = client_jsoncall.result
