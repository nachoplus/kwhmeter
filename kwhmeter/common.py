
import datetime
import pytz 
import os
from pathlib import Path
import yaml
from yaml.loader import SafeLoader
from workalendar.europe import Spain
import logging

timezone = pytz.timezone("Europe/Madrid")

home = str(Path.home())
data_dir=os.getenv('KALPA_HOME',f"{home}/.kalpa")
credenciales_file=f'{data_dir}/distribuidoras.yml'
pvpc_data_file=f'{data_dir}/esios_pvpc.pkl'


def periodo_tarifario(fecha_hora:datetime.datetime)->str:
    fechahora=fecha_hora-datetime.timedelta(hours=1)
    spain_calendar=Spain()
    holidays=spain_calendar.holidays(fechahora.year)    
    if fechahora in [x[0] for x in holidays]:
        return 'P3'
    if fechahora.weekday()==5 or fechahora.weekday()==6:
        return 'P3'
    elif fechahora.hour <= 7 and fechahora.hour >=0:
        return 'P3'
    elif fechahora.hour in [8,9,14,15,16,17,22,23]:
        return 'P2'
    else:
        return 'P1'

def read_config():
    if os.path.exists(credenciales_file):
        with open(credenciales_file,'r') as f:
            credenciales = yaml.load(f, Loader=SafeLoader)    
    else:
        logging.error(f'No existe el fichero de credenciales: {credenciales_file}')
        return False
    return credenciales

def write_config(suministro=None,distribuidora=None,user=None,password=None):
    if suministro is None or distribuidora is None or user is None or password is None:
        logging.error("Faltan datos:")
        return False
    dic={suministro:{'distribuidora':distribuidora,'user':user,'password':password}}
    credenciales=read_config()
    if not credenciales:
        logging.info(F'Creando nuevo archivo de credenciales')
        credenciales=dic
    else:
        credenciales.update(dic)
    print(credenciales)
    with open(credenciales_file,'w') as f:
        yaml.dump(credenciales, f, default_flow_style=False)         
    return credenciales


def contador(distribuidora=None,user=None,password=None):
    lista_distribuidoras=['iberdrola','eredes']
    if distribuidora=='iberdrola':
        from .iberdrola import iberdrola as _contador
    elif distribuidora=='eredes':
        from .eredes import eredes as _contador
    else:
        logging.error(f'Distribuidora no soportada:{distribuidora}')
        logging.info(f"solo está soportadas las siguientes distribuidoras:{lista_distribuidoras}")
        exit(1)
    contador=_contador()        
    if not user is None and  not password is None:
        contador.login(user,password)
    else:
        logging.error('Login invalido')
    return contador    