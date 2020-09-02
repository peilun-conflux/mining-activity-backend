# export FLASK_APP=http_server.py
# flask run

# sudo apt install -y python3.7 python3.7-dev
# pip3 install sqlitedict flask jsonrpcclient eth_utils gunicorn asyncio websockets pysha3 py_ecc rlp coincurve flask_cors gevent psutil
python3 chain_data_fetcher.py &
gunicorn -b 0.0.0.0:4000 http_server:app
