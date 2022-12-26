import click
import json
import datetime
from pathlib import Path
import logging
from ..common import contador,read_config, write_config, timezone
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
@click.option('--factura','factura',multiple=True,help="Consumos para las facturas especificadas. Se puede usar tantas veces como facturas se quieran recuperar",show_default=True,default=False)
@click.option('--fecha-ini', 'fecha_ini',type=click.DateTime(formats=["%Y-%m-%d"]),
              default=str(datetime.date.today()-datetime.timedelta(days=30)),help="Fecha inicio consumos por fecha",show_default=True)
@click.option('--fecha-fin', 'fecha_fin',type=click.DateTime(formats=["%Y-%m-%d"]),
              default=str(datetime.date.today()),help="Fecha fin consumos por fecha",show_default=True)
@click.option('--precios',is_flag=True, show_default=True, default=False, help="Añade los precios a cada hora")              
@click.option('--format',help="Formato de salida",
              type=click.Choice(['screen','cnmc_csv', 'excel','html'], case_sensitive=False),default='screen',show_default=True)
@click.option('--fichero',show_default=True,default='consumos',help='Fichero de salida (sin extensión)')              
def get_data(suministro,lista_facturas,factura,fecha_ini,fecha_fin,precios,format,fichero):
    credenciales=read_config()
    if not credenciales:
        logging.error("No existe archivo de credenciales")
        return False
    elif not suministro in credenciales:
        logging.error(f"El archivo de credenciales no contiene el suministro:{suministro}")
        return False
    _contador=contador(**credenciales[suministro])
    if True:
        print(f'TITULAR: {_contador.titular} CUPS:{_contador.cups}')
        print(f'DIRECCION: {_contador.direccion}')
        print(f'POTENCIA CONTRATADA {_contador.potencias}')
    if lista_facturas:
        print("Peridos de facturacion disponibles:")
        df=_contador.facturas()
        print(df)
        return
    elif factura:
        factura=list(factura)
        print(f"Consumos de la facturas:{factura}")
        df=_contador.consumo_facturado(factura)
    elif fecha_fin and fecha_ini:
        fecha_ini=timezone.localize(fecha_ini)
        fecha_fin=timezone.localize(fecha_fin)
        print(f"Consumos entre las fechas {fecha_ini} y {fecha_fin}")
        df=_contador.consumo(fecha_ini,fecha_fin)
    else:
        print("No se han especificado parametros")
        return
    if precios:
        df=append_prices(df)
    if format=='screen':
        print(df)
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
        df['CUPS']=_contador.cups        
        df['Fecha']=df['fecha'].dt.strftime('%d/%m/%Y')
        df['Hora']=df['fecha'].dt.hour
        df['Consumo_kWh']=df['consumo']/1000
        df['Metodo_obtencion']=df['tipo']
        df[['CUPS','Fecha','Hora','Consumo_kWh','Metodo_obtencion']].to_csv(f'{fichero}.csv',index=False,decimal=',',sep=';')        
    elif format=='html':
        df.to_html(f'{fichero}.html')              