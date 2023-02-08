from datetime import datetime, timedelta
import pytz
import pandas as pd
import logging
from requests import Session
from .common import periodo_tarifario, timezone
from .pvpc import pvpc
from .exception import LoginException, ResponseException, NoResponseException,  \
    SessionException

logging.basicConfig(level=logging.INFO)

class iberdrola:

    __domain = "https://www.i-de.es"
    __login_url = __domain + "/consumidores/rest/loginNew/login"
    __obtener_facturas_url = __domain + "/consumidores/rest/consumoNew/obtenerDatosFacturasConsumo/fechaInicio/{}00:00:00/fechaFinal/{}00:00:00/" ## date format: 07-11-2020 - that's 7 Nov 2020
    __obtener_potenciasMax_url = __domain + '/consumidores/rest/consumoNew/obtenerPotenciasMaximasRangoV2/{}00:00:00/{}00:00:00'
    __obtener_consumo_contador_url = __domain + "/consumidores/rest/consumoNew/obtenerDatosConsumoPeriodo/fechaInicio/{}00:00:00/fechaFinal/{}00:00:00/" # date format: 07-11-2020 - that's 7 Nov 2020    
    __obtener_consumo_facturado_url = __domain + '/consumidores/rest/consumoNew/obtenerDatosConsumoFacturado/numFactura/{}/fechaDesde/{}00:00:00/fechaHasta/{}00:00:00/'
    __obtener_consumo_discriminación_horaria_url = __domain + '/consumidores/rest/consumoNew/obtenerDatosConsumoDH/{}/{}/dias/USU/'
    __detalle_contrato_url = __domain + "/consumidores/rest/detalleCto/detalle/"
    __detalle_PS_url = __domain + "/consumidores/rest/infoPS/datos/"


    __headers = {

        'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/77.0.3865.90 Chrome/77.0.3865.90 Safari/537.36",
        'accept': "application/json; charset=utf-8",
        'content-type': "application/json; charset=utf-8",
        'cache-control': "no-cache"
    }

    def __init__(self, session=None):
        """Iber class __init__ method."""
        self.__session = session

    def login(self, user, password, session=Session()):
        """Creates session with your credentials"""
        self.__session = session
        login_data = "[\"{}\",\"{}\",null,\"Linux -\",\"PC\",\"Chrome 77.0.3865.90\",\"0\",\"\",\"s\"]".format(user, password)
        response = self.__session.request("POST", self.__login_url, data=login_data, headers=self.__headers)
        if response.status_code != 200:
            self.__session = None
            raise ResponseException(response.status_code)
        json_response = response.json()
        if json_response["success"] != "true":
            self.__session = None
            raise LoginException(user)
        self.contrato=self.contrato()
        self.infoPS=self.infoPS()
        self.potencias={'P1':float(self.infoPS['val_POT_P1'])/1000,'P2':float(self.infoPS['val_POT_P2'])/1000}
        self.cups=self.contrato['cups'].strip()
        self.direccion=f"{self.infoPS['tit_DIREC'].strip()} {self.infoPS['tit_POBLA'].strip()} {self.infoPS['tit_COD_POST'].strip()}-{self.infoPS['tit_PROVIN'].strip()}"
        self.titular=f"{self.contrato['nomTitular'].strip()} {self.contrato['ape1Titular'].strip()} {self.contrato['ape2Titular'].strip()}"
        self.DNI={self.contrato['dni'].strip()}
        self.datos={'potencias':self.potencias,'cups':self.cups,'direccion':self.direccion,'titular':self.titular,'DNI':self.DNI}
        to_day = datetime.now(timezone)-timedelta(days=0)
        from_day=to_day-timedelta(days=365*5)                #Maximo 5 años
        self.lista_facturas=self._facturas(from_day,to_day)
        self.nfacturas=self.lista_facturas.shape[0]
        self.factura_fechamin=self.lista_facturas.fechaInicio.min()
        self.factura_fechamax=self.lista_facturas.fechaFin.max()
        logging.info(f'Existen {self.nfacturas} facturas. Desde: {self.factura_fechamin} hasta:{self.factura_fechamax}')

    def _facturas(self,start,end):
        self.__check_session()
        facturas=self.virtual_call(self.__obtener_facturas_url,start,end)['facturas']
        if len(facturas)==0:
            return pd.DataFrame(columns=['fechaInicio','fechaFin','numero'])
        df=pd.DataFrame(facturas)
        df['fecha']=pd.to_datetime(df['fecha'],format='%d/%m/%Y')
        df['fecha']=df['fecha'].apply(lambda x: f'{x.date()}')
        df.set_index('fecha',inplace=True)
        df.index.name='factura'
        df.rename({'fechaHasta':'fechaFin','fechaDesde':'fechaInicio'},axis=1,inplace=True)
        df['fechaInicio']=pd.to_datetime(df['fechaInicio'],format='%d/%m/%Y').apply(lambda x:timezone.localize(x))
        df['fechaFin']=pd.to_datetime(df['fechaFin'],format='%d/%m/%Y').apply(lambda x:timezone.localize(x+timedelta(hours=24)))  #hasta el final del dia      
        return df[['fechaInicio','fechaFin','numero']]

    def __check_session(self):
        if not self.__session:
            raise SessionException()

    def consumo_contador(self,start,end):
        self.__check_session()
        con_contador_json=self.virtual_call(self.__obtener_consumo_contador_url,start,end)
        result=[]
        v=con_contador_json
        start_time=datetime.strptime(v['fechaPeriodo'],'%d-%m-%Y%H:%M:%S')
        for i,d in enumerate(v['y']['data'][0]):
            #los consumos se apuntan en la hora correpondiente al final del periodo i.e periodo 0-1 se apunta en la hora 01:00
            if not d is None:
                new={'fecha': timezone.localize(start_time)+timedelta(hours=i),'factura':'en curso','consumo':d['valor'],'tipo':'R'}
                result.append(new)                    

        if len(result)==0:
            logging.error(f"No existen consumos de contador entre las fechas {start} - {end}")
            return False

        df=pd.DataFrame(result).set_index('fecha').sort_index()
        df.index.name='fecha'
        df['consumo']=df['consumo'].astype(float)   
        df['periodo']=df.index.map(periodo_tarifario)     
        return df

    def consumo_facturado(self,lista_periodos):
        self.__check_session()
        facturas=self.lista_facturas                       
        facturas=facturas.loc[lista_periodos]
        if facturas.shape[0]==0:
            logging.error(f"no existen los periodos de facturas especificados: {lista_periodos}")
            return False
        cc={}
        result=[]
        for index,factura in facturas.iterrows():
            start=factura['fechaInicio']
            fechaDesde=start.strftime('%d-%m-%Y')
            end=(factura['fechaFin']-timedelta(hours=24))
            fechaHasta=end.strftime('%d-%m-%Y')
            numero=factura['numero']
            #fechaDesde=factura['fechaInicio'].strftime('%d-%m-%Y')
            #fechaHasta=(factura['fechaFin']-timedelta(hours=24)).strftime('%d-%m-%Y')
            url= self.__obtener_consumo_facturado_url.format(numero,fechaDesde, fechaHasta)
            logging.debug(url)
            response = self.__session.request("GET",url,headers=self.__headers)
            if response.status_code != 200:
                raise ResponseException(response.status_code)
            if not response.text:
                raise NoResponseException
            logging.debug(response.json())
            cc[numero]=response.json()

        for k,v in cc.items():
            start_time=datetime.strptime(v['fechaPeriodo'],'%d-%m-%Y%H:%M:%S')
            for i,d in enumerate(v['y']['data'][0]):
                #los consumos se apuntan en la hora correpondiente al final del periodo i.e periodo 0-1 se apunta en la hora 01:00
                new={'fecha': timezone.localize(start_time)+timedelta(hours=i),'factura':k,'consumo':d['valor'],'tipo':d['tipo']}
                result.append(new)                    
                #if not d is None:
                #    new={'fecha': timezone.localize(start_time)+timedelta(hours=i),'factura':k,'consumo':d['valor'],'tipo':d['tipo']}
                #    result.append(new)

        if len(result)==0:
            logging.error(f"No existen consumos facturados entre las fechas {start} - {end}")
            return False

        df=pd.DataFrame(result).set_index('fecha').sort_index()
        df.index.name='fecha'
        df['consumo']=df['consumo'].astype(float)
        df['periodo']=df.index.map(periodo_tarifario)
        df['factura_iberdrola']=df['factura']       
        for k,v in self.lista_facturas.to_dict(orient='index').items():
            df.loc[v['fechaInicio']:v['fechaFin'],'factura']=k
        return df

    def consumo(self,start,end):
        #recuperamos el consumo facturado que tiene ya los estimados y es mas fiable
        facturas=self.lista_facturas 
        mask= (facturas['fechaInicio']>=start) & (facturas['fechaInicio']<=end) | (facturas['fechaFin']>=start) & (facturas['fechaFin']<=end) 
        #| (facturas['fechaInicio']<=end & facturas['fechaFin']>=start)
        lista_fac=facturas[mask].index.to_list()
        logging.debug(f'Recuperando periodos de facturación:{lista_fac}')
        con_facturado=self.consumo_facturado(lista_fac)
        #si el periodo es mayor que lo registrado en el consumo facturado
        #lo completamos con el consumo contador
        if con_facturado is False:
            df=self.consumo_contador(start,end)
        else:
            df=con_facturado
            if con_facturado.index.max() < end:
                con_contador=self.consumo_contador(con_facturado.index.max(),end)  
                if not con_contador is False:
                   df=pd.concat([df,con_contador])
        df.sort_index(inplace=True)                   
        realend=min(df.index.max(),end)
        return df[start:realend]


    def virtual_call(self,url,start,end):
        start_str = start.strftime('%d-%m-%Y')
        end_str = end.strftime('%d-%m-%Y')        
        url=url.format(start_str, end_str)
        logging.debug(url)
        response = self.__session.request("GET", url.format(start_str, end_str),headers=self.__headers)
        if response.status_code != 200:
            raise ResponseException(response.status_code)
        if not response.text:
            raise NoResponseException
        return response.json()             

    def consumos_discriminación_horaria(self,start,end):
        self.__check_session()
        return self.virtual_call(self.__obtener_consumo_discriminación_horaria_url,start,end)



    def facturas(self):
        return self.lista_facturas

    def maximetro(self,start,end):
        self.__check_session()
        potencias_max_json=self.virtual_call(self.__obtener_potenciasMax_url,start,end)['potMaxMens']       
        data=[]
        for k,v in {'valle':[mes[0] for mes in potencias_max_json],'punta':[mes[1] for mes in potencias_max_json]}.items():
            for d in v:
                new=d.copy()
                new.update({'periodo':k})
                data.append(new)
        df=pd.DataFrame(data)
        df.columns=['fecha','mes','maximetro','periodo']
        df['fecha']=pd.to_datetime(df['fecha'],format='%d/%m/%Y %H:%M').apply(lambda x: timezone.localize(x))
        df['maximetro']=df['maximetro'].astype(float)
        df['mes']=df['mes'].astype(int)
        return df.set_index('fecha').sort_index()
   
    def contrato(self):
        self.__check_session()
        response=self.__session.request("GET",self.__detalle_contrato_url ,headers=self.__headers)
        datos=response.json()
        return datos

    def infoPS(self):
        response=self.__session.request("GET",self.__detalle_PS_url ,headers=self.__headers)
        datos=response.json()
        return datos
        