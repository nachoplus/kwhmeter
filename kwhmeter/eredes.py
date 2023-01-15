from datetime import datetime, timedelta
import json
import pytz
import base64
import pandas as pd
from requests import Session
from .common import periodo_tarifario, timezone
from .pvpc import pvpc
from .exception import LoginException, ResponseException, NoResponseException,  \
    SessionException
import logging

logging.basicConfig(level=logging.INFO)

class eredes:

    __domain = "https://srv.misconsumos.eredesdistribucion.es"
    __login_url = __domain + "/services/es.edp.consumos.Login"
    __consumos_url = __domain + "/services/es.edp.consumos.Consumos"
    __potencias_max_url = __domain + "/services/es.edp.consumos.Potencias"    
    __datos_suministro_url = __domain + "/services/es.edp.consumos.Suministro"


    __headers = {
        'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/77.0.3865.90 Chrome/77.0.3865.90 Safari/537.36",
        'accept': "application/json; charset=utf-8",
        'content-type': "application/json; charset=utf-8",
        'cache-control': "no-cache",
        'apikey': 'bWlzY29uc3Vtb3M6ZWRwc2VjdXJldG9rZW4'
    }

    def __init__(self, session=None):
        """Iber class __init__ method."""
        self.__session = session

    def fix_date(self,x):
        h=int(x.split(' ')[1].split(':')[0])
        if h==24:
            m=int(x.split(' ')[1].split(':')[1])
            d=x.split(' ')[0]
            result=timezone.localize(datetime.strptime(f'{d} 00:00','%d/%m/%Y %H:%M'))+timedelta(days=1)       
        else:
            result=timezone.localize(datetime.strptime(x,'%d/%m/%Y %H:%M'))
        return result    

    def login(self, user, password, session=Session()):
        """Creates session with your credentials"""
        self.__session = session
        jsondata=    {
            "jsonrpc": "2.0",
            "method": "login",
            "id": 1670280283976,
            "params": {
                "document": user,
                "password":  str(base64.b64encode(password.encode("utf-8")),'utf-8')
            }
            }   
        response = self.__session.request("POST", self.__login_url, json=jsondata, headers=self.__headers)
        if response.status_code != 200:
            self.__session = None
            raise ResponseException(response.status_code)
        json_response = response.json()
        if not 'result' in json_response:
            logging.warning(f"No result in response:{response.json()}")  
            self.__session = None
            raise LoginException(user)
        elif 'error' in json_response['result']:
            logging.error(f"error:{json_response['result']}")
            self.__session = None
            raise LoginException(user)
            
        self._login_data=json.loads(json_response['result'])
        self.accessToken=self._login_data['accessToken']
        self.__headers.update({'sessionkey':self.accessToken})

        self.cups=self._login_data['cups'].strip()
        self.titular=f"{self._login_data['name'].strip()} {self._login_data['surname'].strip()}"
        self.DNI=self._login_data['document'].strip()

        self.infoPS=self.infoPS()[0]
        self.direccion=self.infoPS['DIR'].strip()
        self.potencias={'P1':float(self.infoPS['POTENCIA'][0]),'P2':float(self.infoPS['POTENCIA'][1])}
        self.lista_facturas=self._facturas()
        self.nfacturas=self.lista_facturas.shape[0]
        self.factura_fechamin=self.lista_facturas.fechaInicio.min()
        self.factura_fechamax=self.lista_facturas.fechaFin.max()
        print(f'Existen {self.nfacturas} facturas. Desde: {self.factura_fechamin} hasta:{self.factura_fechamax}')

    def __check_session(self):
        if not self.__session:
            raise SessionException()

    def _facturas(self):
        self.__check_session()        
        jsondata={
            "jsonrpc": "2.0",
            "method": "getPeriodosConsumos",
            "id": 1670441265144,
            "params": {
                "cups":self.cups
            }            
        }
        response = self.__session.request("POST", self.__consumos_url, json=jsondata, headers=self.__headers)   
        if response.status_code != 200:
            raise ResponseException(response.status_code)
        if not 'result' in  response.json():
            logging.warning(f"No result in response:{response.json()}")  
        data=json.loads(response.json()['result'])
        df=pd.DataFrame(data['periodos'])    
        df['fechaInicio']=pd.to_datetime(df['fechaInicio'],format='%d-%m-%Y').apply(lambda x:timezone.localize(x+timedelta(days=1)))        
        df['fechaFin']=pd.to_datetime(df['fechaFin'],format='%d-%m-%Y').apply(lambda x:timezone.localize(x+timedelta(hours=0)))  #hasta el final del dia
        df.index=(df['fechaFin']).apply(lambda x: f'{(x+timedelta(days=1)).date()}')        
        df.index.name='factura'
        df.sort_index(inplace=True,ascending=False)
        return df

    def consumo_facturado(self,lista_periodos):
        self.__check_session()
        facturas=self.lista_facturas
        facturas=facturas.loc[lista_periodos]
        if facturas.shape[0]==0:
            logging.error(f"no existen los periodos de facturas especificados: {lista_periodos}")
            return False        
        start=facturas['fechaInicio'].min()
        end=facturas['fechaFin'].max()
        return self.consumo(start,end)[start:end]
 

    def consumo(self,start,end):
        self.__check_session()
        facturas=self.lista_facturas
        start_str = start.strftime('%d/%m/%Y')
        end_str = end.strftime('%d/%m/%Y')
        jsondata=        {
        "jsonrpc": "2.0",
        "method": "getConsumos",
        "id": 1670366135091,
        "params": {
            "cups": self.cups,
            "fechaInicio": start_str,
            "fechaFin": end_str,
            "sector": "03"
        }
        }
        response = self.__session.request("POST", self.__consumos_url, json=jsondata, headers=self.__headers)
        if response.status_code != 200:
            raise ResponseException(response.status_code)
        if not 'result' in  response.json():
            logging.warning(f"No result in response:{response.json()}")        
        data=json.loads(response.json()['result'])
        df=pd.DataFrame(data)
        df['fecha']=df['datetime'].apply(lambda x:self.fix_date(x))
        df['consumo']=df['consumo'].astype(float)*1000
        df['tipo']=df['estimated'].apply(lambda x: x.upper())
        df.drop(['datetime','estimated'],axis=1,inplace=True)
        df.set_index('fecha',inplace=True)
        df.sort_index(inplace=True)
        df.index.name='fecha'
        df['periodo']=df.index.map(periodo_tarifario)
        for k,v in facturas.to_dict(orient='index').items():
            df.loc[v['fechaInicio']:v['fechaFin'],'factura']=k
        #Los consumos sin numero de factura y posteriores a la ultima factura
        #se asignan a una supuesta factura 'en curso'
        ultimafechafactura=facturas['fechaFin'].max()
        mask= df['factura'].isna() & (df.index >ultimafechafactura)
        df.loc[ mask ,'factura']='en curso'

        #se borran los registros sin consumo
        df.dropna(subset=['consumo'],inplace=True)
        return df[start:end]

    def facturas(self):
        return self.lista_facturas



    def maximetro(self,start,end):
        self.__check_session()        
        jsondata={
                "jsonrpc": "2.0",
                "method": "getPotencias",
                "id": 1670441265160,
                "params": {
                    "cups": "ES0026000000273781LM0F"
                }
            }
        response = self.__session.request("POST", self.__potencias_max_url, json=jsondata, headers=self.__headers)    
        data=json.loads(response.json()['result'])
        df=pd.DataFrame(data)
        return data

    def infoPS(self):
        self.__check_session()        
        jsondata={
                "jsonrpc": "2.0",
                "method": "getListadoSuministros",
                "id": 1670441265160,
                "params": None
            }
        response = self.__session.request("POST", self.__datos_suministro_url, json=jsondata, headers=self.__headers)    
        data=json.loads(response.json()['result'])  
        return data      