import argparse
import uvicorn
from .app import create_app


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8788)
    args=parser.parse_args()
    uvicorn.run(create_app(),host='127.0.0.1',port=args.port,proxy_headers=False,access_log=False)


if __name__=='__main__':main()
