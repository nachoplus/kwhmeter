import click
import json
import numpy as np
import datetime
from pathlib import Path
import logging
from ..common import contador,read_config, write_config, timezone, flex_consumos
from ..pvpc import append_prices
from pandas.api.types import is_datetime64_any_dtype as is_datetime

class DateTimeEncoder(json.JSONEncoder):
        #Override the default method
        def default(self, obj):
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()

#Alta o modificación de suministro
@click.command()
@click.argument('suministro',type=str)
@click.argument('distribuidora',type=str)
@click.argument('user',type=str)
@click.argument('password',type=str)
def set_credenciales(suministro,distribuidora,user,password):
    write_config(suministro,distribuidora,user,password)

#datos
@click.command()
@click.argument('suministro',type=str)
@click.option('--lista-facturas',is_flag=True, show_default=True, default=False, help="Muestra los periodos de facturación disponibles")
@click.option('--n',multiple=True,type=click.INT,help="Consumos para las facturas especificadas por indice. Se puede usar tantas veces como facturas se quieran recuperar",show_default=True,default=False)
@click.option('--m',multiple=False,type=click.INT,help="Consumos para las ultimas m facturas",show_default=True,default=False)
@click.option('--factura','factura',multiple=True,help="Consumos para las facturas especificadas. Se puede usar tantas veces como facturas se quieran recuperar",show_default=True,default=False)
@click.option('--fecha-ini', 'fecha_ini',type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Fecha inicio consumos por fecha",show_default=True)
@click.option('--fecha-fin', 'fecha_fin',type=click.DateTime(formats=["%Y-%m-%d"]),
              help="Fecha fin consumos por fecha",show_default=True)
@click.option('--precios',is_flag=True, show_default=True, default=False, help="Añade los precios a cada hora")              
@click.option('--format',help="Formato de salida",
              type=click.Choice(['screen','cnmc_csv', 'excel','html','pkl'], case_sensitive=False),default='screen',show_default=True)
@click.option('--periodo','-t',help="Periodo a considerar para obtener el valor promedio/acumulado ",
              type=click.Choice(['horario','diario', 'semanal','mensual','anual'], case_sensitive=False),default='horario',show_default=True)              
@click.option('--acumulado/--promedio','-a/-p',help="Periodo a considerar para obtener el valor acumulado ",default=True,show_default=True)              
@click.option('--fichero',show_default=True,default='consumos',help='Fichero de salida (sin extensión)')              
def get_data(suministro,lista_facturas,n,m,factura,fecha_ini,fecha_fin,precios,format,periodo,acumulado,fichero):
    datos,df=flex_consumos(suministro,n,m,factura,fecha_ini,fecha_fin)
    if not datos:
        return
    if precios:
        df=append_prices(df)
    if acumulado:
        fn=sum
    else:
        fn=np.mean
    if periodo=='diario':
        df=df.resample('1D').aggregate(fn)
    elif periodo=='semanal':
        df=df.resample('1W').aggregate(fn)
    elif periodo=='mensual':
        df=df.resample('1M').aggregate(fn)

    if format=='screen':
        print(df)
    elif format=='pkl':
        df.to_pickle(f'{fichero}.pkl')
    elif format=='excel':
        #Excel no soporta tz aware timestamps
        df=df.reset_index()
        for col in df.columns:
            if is_datetime(df[col]):
                df[col]=df[col].dt.tz_localize(None)
        df.to_excel(f'{fichero}.xlsx',index=False)
    elif format=='cnmc_csv':
        #Formato para el simulador de la CNMC
        df=df.reset_index()
        df['CUPS']=datos['cups']
        df['Fecha']=df['fecha'].dt.strftime('%d/%m/%Y')
        df['Hora']=df['fecha'].dt.hour
        df['Consumo_kWh']=df['consumo']/1000
        df['Metodo_obtencion']=df['tipo']
        df[['CUPS','Fecha','Hora','Consumo_kWh','Metodo_obtencion']].to_csv(f'{fichero}.csv',index=False,decimal=',',sep=';')   
        print(f'fichero CNMC:{fichero}.csv creado')     
    elif format=='html':
        df.to_html(f'{fichero}.html')              