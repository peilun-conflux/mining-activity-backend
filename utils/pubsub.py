import asyncio
import json
import websockets

from jsonrpcclient.clients.websockets_client import WebSocketsClient
from jsonrpcclient.requests import Request


class PubSubClient:
    def __init__(self, url):
        self.buffer = {}
        self.url = url
        self.ws = None

    async def subscribe(self, topic, *args):
        # connect if necessary
        if self.ws is None:
            self.ws = await websockets.connect(self.url)

        # subscribe
        req = Request("cfx_subscribe", topic, *args)
        resp = await WebSocketsClient(self.ws).send(req)

        # initialize buffer
        sub_id = resp.data.result
        self.buffer[sub_id] = []
        return Subscription(self, sub_id)


class Subscription:
    def __init__(self, pubsub, sub_id):
        self.pubsub = pubsub
        self.sub_id = sub_id

    async def unsubscribe(self):
        assert (self.pubsub.ws is not None)

        # unsubscribe
        req = Request("cfx_unsubscribe", self.sub_id)
        resp = await WebSocketsClient(self.pubsub.ws).send(req)
        assert (resp.data.result)

        # clear buffer
        del self.pubsub.buffer[self.sub_id]

    async def next_wo_timeout(self):
        # return buffered if possible
        if len(self.pubsub.buffer[self.sub_id]) > 0:
            return self.pubsub.buffer[self.sub_id].pop()

        # receive new
        while True:
            resp = await self.pubsub.ws.recv()
            resp = json.loads(resp)

            recv_id = resp["params"]["subscription"]
            result = resp["params"]["result"]

            if recv_id == self.sub_id:
                return result

            self.pubsub.buffer[recv_id].append(result)

    async def next(self, timeout=1.0):
        try:
            return await asyncio.wait_for(self.next_wo_timeout(), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"Received nothing on pub-sub {self.pubsub.url}/{self.sub_id} (node: {self.pubsub.nid}) for {timeout} seconds.")

    async def iter(self, timeout=0.5):
        while True:
            try:
                yield await self.next(timeout=timeout)
            except TimeoutError:
                break
