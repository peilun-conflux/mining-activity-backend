# export FLASK_APP=http_server.py
# flask run
pip3 install sqlitedict flask jsonrpcclient eth_utils gunicorn
gunicorn -w 1 -b 127.0.0.1:4000 http_server:app
