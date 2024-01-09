import pandas as pd
from datetime import datetime, timedelta
import pytz
import requests
import json
from .common import timezone,data_dir,pvpc_data_file
import os
import logging
import numpy as np

__headers = {

    'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/77.0.3865.90 Chrome/77.0.3865.90 Safari/537.36",
    'accept': "application/json; charset=utf-8",
    'content-type': "application/json; charset=utf-8",
    'cache-control': "no-cache",
}

def pvpc(start,end):
    fechas=pd.date_range(start,end,freq='1D',normalize=True)
    if os.path.exists(pvpc_data_file):
        df=pd.read_pickle(pvpc_data_file).drop_duplicates()
    else:
        PVPC=_pvpc(fechas)
        if isinstance(PVPC,pd.DataFrame):
            df=PVPC.drop_duplicates()
            df.sort_index(inplace=True)        
            df.to_pickle(pvpc_data_file)    
            return df[start:end]
        else:
            return False

    #calculo todos las fechas que no están en el pickle
    fechas_en_cache=pd.DataFrame(df.index,columns=['fecha'],index=df.index)
    fechas_en_cache=fechas_en_cache.resample('1D')[['fecha']].count()
    fechas_en_cache=fechas_en_cache[fechas_en_cache['fecha']>=23]    
    missing_dates=pd.DataFrame(fechas).set_index(0).merge(fechas_en_cache,right_index=True,left_index=True,how='outer',indicator=True)
    missing_dates.to_csv('kk.csv')
    missing_dates=sorted(missing_dates[missing_dates['_merge']=='left_only'].index.to_list())
    logging.info(f'recovering missing dates:{len(missing_dates)}')
    if len(missing_dates)!=0:
        PVPC=_pvpc(missing_dates)
        if isinstance(PVPC,pd.DataFrame):
            df=pd.concat([df,PVPC]).drop_duplicates()
            df.to_pickle(pvpc_data_file)      
    df.sort_index(inplace=True)
    return df[start:end]

def _pvpc(date_list):
    urlbase='https://api.esios.ree.es/archives/70/download_json?locale=es'
    # NOTAS:
    # PCB coste total suma de todos los terminos
    # COF2TD COF Tarifa 2.0 TD (ya aplicado a cada termino)
    # PMHPCB y PMHCYM Mercado diario e intradiario
    # SAHPCB y SAHCYM Servicios de ajuste
    # FOMPCB y FOMCYM Financiación OM
    # FOSPCB y FOSCYM Financiación OS
    # INTPCB y INTCYM Servicio de Ininterrumpibilidad
    # PCAPCB y PCACYM Pago por capacidad
    # TEUPCB y TEUCYM Peajes y cargos
    # CCVPCB y CCVCYM Coste comercialización variable
    # EDSRPCB y EDSRCYM Excedente o déficit subastas renovables
    # EDCGASPCB EXCEDENTE O DÉFICIT MECANISMO AJUSTE COSTE PRODUCCIÓN
    # TAHPCB y TAHCYM termino mercado a plazos
    # Estos terminos están vigentes desde el tope del gas. Para fechas nateriores 
    # hay otros terminos
    has_data=False
    first=True
    for i,fecha in enumerate(list(set(date_list))):
        url=f'{urlbase}&start_date={fecha.isoformat()}&end_date={fecha.isoformat()}&date_type=datos'
        logging.info(f'{i} {url}')
        response=requests.get(url,headers=__headers)
        #print(response.json())
        if not 'PVPC' in response.json():
            logging.warning(f'{i} no hay datos para la fecha:{fecha}')
            continue
        has_data=True
        datos=response.json()['PVPC']
        df=pd.DataFrame(datos)
        for col in df.columns:
            if col in ['Dia','Hora']:
                continue
            df[col]=pd.to_numeric(df[col].str.replace(',', '.'))
        df['timestamp']=pd.to_datetime(df['Dia'],format='%d/%m/%Y')
        df['Periodo']=df['Hora']
        df['Hora']=df['Hora'].str.extract(r'(\d{2})-\d{2}').astype(int)  
        df['Hora'] = np.arange(df.shape[0])
        # TODO ree entrega mal el periodo del cambio de hora de marzo. 
        # pone como periodos 00-01,01-02,03-04 ... 
        # Revisar workarround 
        timezone = pytz.timezone("Europe/Madrid")
        df.index = pd.to_datetime(df['timestamp'].apply(lambda x: timezone.localize(x))+df['Hora'].apply(lambda x: timedelta(hours=x+1))).apply(lambda x: timezone.normalize(x))
        df.drop(['Dia', 'Hora','timestamp'], axis=1, inplace=True) 
        df.drop([col  for col in df.columns if 'CYM' in col],axis=1,inplace=True)  
        if first:
            ddf=df.copy()
            first=False
        else:
            ddf=pd.concat([df,ddf])
    if has_data:
        result=ddf.sort_index()
    else:
        result=False
    return result

def append_prices(df):
        PVPC=pvpc(df.index.min(),df.index.max())
        # PCB Coste total suma de todos los terminos
        # PMHPCB Coste mercado diario e intradiario
        col_list=['PCB','PMHPCB']  
        if 'EDCGASPCB' in PVPC.columns:
            # Termino de ajuste gas excepcion iberica
            col_list.append('EDCGASPCB')
        if 'TEUPCB' in PVPC.columns:
            # Termino de peajes ycargos
            col_list.append('TEUPCB')
        if 'TAHPCB' in PVPC.columns:
            # Termino de ajuste mercado a plazos
            col_list.append('TAHPCB')    
        df=df.merge(PVPC[col_list],left_index=True,right_index=True,how='left')
        df.rename({ col:f'{col}_PRICE' for col in col_list},axis=1,inplace=True)
        for col in col_list:
            df[col]=df['consumo']*df[f'{col}_PRICE']/1000000
        df.index.name='fecha'            
        return df