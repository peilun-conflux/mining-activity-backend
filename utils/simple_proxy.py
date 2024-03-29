import jsonrpcclient.client
from jsonrpcclient.exceptions import ReceivedErrorResponseError

jsonrpcclient.client.request_log.propagate = False
jsonrpcclient.client.response_log.propagate = False


class SimpleRpcProxy:
    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        from jsonrpcclient.clients.http_client import HTTPClient
        self.client = HTTPClient(url)

    def __getattr__(self, name):
        return RpcCaller(self.client, name, self.timeout)


class RpcCaller:
    def __init__(self, client, method, timeout):
        self.client = client
        self.method = method
        self.timeout = timeout

    def __call__(self, *args, **argsn):
        if argsn:
            raise ValueError('json rpc 2 only supports array arguments')
        from jsonrpcclient.requests import Request
        request = Request(self.method, *args)
        try:
            response = self.client.send(request, timeout=self.timeout)
            return response.data.result
        except Exception as e:
            if isinstance(e, ReceivedErrorResponseError):
                print(f"rpc exception code {e.response.code}, message: {e.response.message}, data: {e.response.data}")
            raise e
