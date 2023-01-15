import logging
from .iberdrola import iberdrola
from .eredes import eredes
from .common import suministro,contador,timezone,data_dir, read_config
from .pvpc import pvpc,append_prices
import os

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

if not os.path.exists(data_dir):
   os.makedirs(data_dir)
   logging.warning(f"data dir created:{data_dir}")   
else:
   logging.debug(f"data dir already exists:{data_dir}") 

