from datetime import datetime, timedelta
import re
import pandas as pd
from .common import periodo_tarifario, timezone, daterange
from .pvpc import pvpc
import logging

from .EdistribucionAPI import Edistribucion
logging.getLogger().setLevel(logging.ERROR)


class endesa:

    def __init__(self):
        pass
        #with open('credentials.py','w') as fd:
        #    fd.write('#BORRAME')

    def __del__(self):
        import os
        for fi in ['edistribucion.access','edistribucion.session']:
            if os.path.exists(fi):
                os.remove(fi)

    def login(self, user, password):     
        self.edis = Edistribucion(login=user,password=password)
        r = self.edis.get_cups()
        cups = self.edis.get_list_cups()[-1]
        self.contador=cups['Id']
        #print('Cups: ',cups['Id'])
        info = self.edis.get_cups_info(cups['CUPS_Id'])
        #print(info)  
        self.cups=info['data']['Name'].strip()
        self.titular=""
        self.DNI=""
        self.infoPS=info
        self.direccion=info['data']['Direccion'].strip()
        self.potencias={'P1':float(info['data']['potenciaContratada']),'P2':float(info['data']['potenciaContratada'])}
        self.datos={'potencias':self.potencias,'cups':self.cups,'direccion':self.direccion,'titular':self.titular,'DNI':self.DNI}
        self.cycles = self.edis.get_list_cycles(self.contador)
        new_cycles= {item['value']:re.findall('(\d+\/\d+\/\d+)',item['label']) for item in self.cycles}
        facturas=pd.DataFrame.from_dict(new_cycles,orient='index').reset_index().rename({0:'fechaInicio',1:'fechaFin','index':'numero'},axis=1)
        facturas['fechaInicio']=pd.to_datetime(facturas['fechaInicio'],format='%d/%m/%Y').apply(lambda x:timezone.localize(x+timedelta(days=0))) 
        facturas['fechaFin']=pd.to_datetime(facturas['fechaFin'],format='%d/%m/%Y').apply(lambda x:timezone.localize(x+timedelta(days=1)))  #hasta el final del dia
        facturas.index=(facturas['fechaFin']).apply(lambda x: f'{(x+timedelta(days=0)).date()}')
        facturas.index.name='factura'
        self.lista_facturas=facturas
        self.nfacturas=self.lista_facturas.shape[0]
        self.factura_fechamin=self.lista_facturas.fechaInicio.min()
        self.factura_fechamax=self.lista_facturas.fechaFin.max()
        print(f'Existen {self.nfacturas} facturas. Desde: {self.factura_fechamin} hasta:{self.factura_fechamax}')

 
    def consumo_facturado(self,lista_periodos):
        facturas=self.lista_facturas.reset_index()        
        mask = facturas.factura.isin(lista_periodos)
        facturas=facturas[mask]
        if facturas.shape[0]==0:
            logging.error(f"no existen los periodos de facturas especificados: {lista_periodos}")
            return False
        first=True
        for index,factura in facturas.iterrows():
            meas = self.edis.get_meas(self.contador, self.cycles[index])
            for i,mday in enumerate(meas):
                if i==0:
                    ddf=pd.DataFrame(mday)
                else:
                    ddf=pd.concat([ddf,pd.DataFrame(mday)])
            ddf['factura_endesa']=factura['numero']
            ddf['factura']=factura['factura']
            if first:
                first=False
                df=ddf
            else:
                df=pd.concat([df,ddf])
        #limpieza
        df['_fecha']=pd.to_datetime(df.date,format='%d/%m/%Y')   
        df['fecha']=df.apply(lambda row: timezone.localize(row['_fecha'])+timedelta(hours=row['hourCCH']),axis=1)
        df['consumo']=df['valueDouble']*1000            
        df.drop(['date','hourCCH','hour','valueDouble','invoiced','typePM','cups','date_fileName','real','value'],axis=1,inplace=True)                            
        df.rename({'obtainingMethod':'tipo'},axis=1,inplace=True)
        df.set_index('fecha',inplace=True)
        df.loc[:,'periodo']=df.index.map(periodo_tarifario)            
        df=df[['factura','consumo','periodo','tipo','factura_endesa']]
        return df

    def consumo(self,start,end):
        #recuperamos el consumo facturado que tiene ya los estimados y es mas fiable
        facturas=self.lista_facturas 
        mask= (facturas['fechaInicio']>=start) & (facturas['fechaInicio']<=end) | (facturas['fechaFin']>=start) & (facturas['fechaFin']<=end) | (facturas['fechaInicio']<=end) & (facturas['fechaFin']>=start)
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
        df.dropna(subset='consumo',inplace=True)                   
        return df[start:end]

    def consumo_contador(self,start,end):
        #La API no funciona como debe y hay que pedir los 
        #consumos dia a dia
        for i,d in enumerate(daterange(start,end)):
            start_str = d.strftime('%Y-%m-%d')
            meas=self.edis.get_meas_interval(self.contador, start_str, None)
            if i==0:
                df=pd.DataFrame(meas[0])
            else:
                df=pd.concat([df,pd.DataFrame(meas[0])])
        df['factura_endesa']=None
        df['factura']="En curso"
        #limpieza
        df['_fecha']=pd.to_datetime(df.date,format='%d/%m/%Y')   
        df['fecha']=df.apply(lambda row: timezone.localize(row['_fecha'])+timedelta(hours=row['hourCCH']),axis=1)
        df['consumo']=df['valueDouble']*1000            
        df.drop(['date','hourCCH','hour','valueDouble','invoiced','typePM','cups','date_fileName','real','value'],axis=1,inplace=True)                            
        df.rename({'obtainingMethod':'tipo'},axis=1,inplace=True)
        df.set_index('fecha',inplace=True)
        df.loc[:,'periodo']=df.index.map(periodo_tarifario)            
        df=df[['factura','consumo','periodo','tipo','factura_endesa']]        
        return df

    def facturas(self):
        return self.lista_facturas
