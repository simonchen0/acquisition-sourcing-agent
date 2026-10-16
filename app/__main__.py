import uvicorn
from . import config

if __name__ == '__main__':
    print(f'Acquisition Sourcing Agent → http://{config.HOST}:{config.PORT}')
    uvicorn.run('app.main:app', host=config.HOST, port=config.PORT, log_level='warning')
