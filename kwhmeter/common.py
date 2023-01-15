
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
data_dir=os.getenv('KWHMETER_HOME',f"{home}/.kwhmeter")
credenciales_file=f'{data_dir}/distribuidoras.yml'
pvpc_data_file=f'{data_dir}/esios_pvpc.pkl'


def periodo_tarifario(fecha_hora:datetime.datetime)->str:
    fechahora=fecha_hora-datetime.timedelta(hours=1)
    spain_calendar=Spain()
    holidays=spain_calendar.holidays(fechahora.year)    
    if fechahora.date() in [x[0] for x in holidays]:
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

def suministro(domicilio):
    credenciales=read_config()
    suministro = contador(**credenciales[domicilio])
    return suministro

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

def flex_consumos(domicilio,n=False,factura=False,fecha_ini=False,fecha_fin=False):
    '''
    recupera los consumos de un suministros basandose en uno 
    de los siguienetes datos:
    * el numero de orden de la factura
    * el nombre (fecha) de la factura
    * un periodo entre fechas
    Los datos no usados deben ser False
    '''
    _suministro=suministro(domicilio)
    datos=_suministro.datos
    if n and n[0]==0: 
        f=_suministro.facturas()
        fecha_ini=f.fechaFin[0]+datetime.timedelta(hours=1)
        fecha_fin=timezone.localize(datetime.datetime.now())
        print(f"FACTURA EN CURSO. Fechas {fecha_ini} y {fecha_fin}")
        df=_suministro.consumo(fecha_ini,fecha_fin)        
    elif n:
        f=_suministro.facturas()
        facturas=[]
        for i in n:
            facturas.append(f.index[int(i)-1])
        print(f'CONSUMO DE LAS FACTURAS:{facturas}')
        df=_suministro.consumo_facturado(facturas)
    elif factura:
        factura=list(factura)
        print(f"CONSUMO DE LAS FACTURAS:{factura}")
        df=_suministro.consumo_facturado(factura)
    elif fecha_fin and fecha_ini:
        fecha_ini=timezone.localize(fecha_ini)+datetime.timedelta(hours=1)
        fecha_fin=timezone.localize(fecha_fin)+datetime.timedelta(hours=1)
        print(f"Consumos entre las fechas {fecha_ini} y {fecha_fin}")
        df=_suministro.consumo(fecha_ini,fecha_fin)
    else:
        print("Peridos de facturacion disponibles:")
        df=_suministro.facturas()
        df=df.reset_index()
        df.index=range(1,df.shape[0]+1)
        print(df)
        print()
        print("Para elegir los consumos de una factura concreta usa:")
        print("\t--n [numero factura]. Por ejemplo --n 1 para la última")
        print(f"\t--factura [factura]. Por ejemplo --factura {df.factura[1]} para la última")
        print("Estos argumentos se pueden repetir para considerar varios periodos de facturación:")
        print("\tPor ejemplo --n 1 --n 2 para las dos última")
        print(f"\tPor ejemplo --factura {df.factura[1]} --factura {df.factura[2]} para la dos última")
        print()
        print("Para elegir la factura en curso:")
        print("\t--n 0")        
        print()
        print("Tambien se puede solicitar los consumos entre dos fechas con los argumento:")
        print("\t--fecha-ini [fecha inicial] --fecha-fin [fecha final]")
        return False, False
    return datos,df
        