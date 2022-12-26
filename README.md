# kWhmeter

Clientes para la lectura de contadores electricos de distribuidoras españolas. 

IMPORTANTE: Este software no está vinculado con ninguna compañia electrica. Es un proyecto personal que se pone a disposición de todo el que quiera utilizarlo bajo su propia responsabilidad.

Este software está inspirado por: https://github.com/hectorespert/python-oligo 

De momento está soportados contadores de las redes de:

* I-DE (Grupo Iberdrola). Identificativo: 'iberdrola'
* EREDES DISTRIBUCION (Total Energies. Antiguo HC o EDP). Identificativo: 'eredes'

Para poder consultar el contador es necesario darse de alta previamente en la correspondiente web y que los datos se obtiene de esa pagina mediante técnicas de webscraping. Las webs de las distribuidoras son:

* I-DE: https://www.i-de.es/consumidores/web/guest/login
* EREDES: https://misconsumos.eredesdistribucion.es/

Adicionalmente optiene los precios de la energia oficiales de la web de REE https://www.esios.ree.es/es/pvpc. Recupera los segmentos:

* EDCGASPCB: Precio por el concepto de 'tope al gas'
* TEUPCB: Precio correspondiente a los peajes y cargos
* PCB: Precio total para el PVPC. Incorpora los dos anteriores mas el precio de la energia en los mercados mayoristas y otros conceptos menores.

Este programa utiliza el directorio definido en la variable de entorno KWHMETER_HOME para almacenar las credenciales y el cache de precios del eSios. Por defecto KWHMETER_HOME es $HOME/.kwhmeter

IMPORTANTE: Tanto los valores de energia como los de precio se almacenan a hora venciada. Es decir p.e. el consumo desde las 7:00 hasta las 7:59 se almacena con la marca de tiempo 8:00. Se tiene en cuenta el dia de cambio de hora y las timestamp están 'localizados' para la españa peninsular.

## Uso

Existen dos ejecutables de la linea de comandos (CLI): 

* kwhmeter_set_credenciales SUMINISTRO DISTRIBUIDORA USER PASSWORD. Mediante este comando se crea o actualiza el fichero de configuración $KWHMETER_HOME/credenciales.yml donde se almacenan las credenciales correspondientes a un suministro concreto. 
* kwhmeter. Es el comando principal mediante el cual se recuperan las medidas

> kwhmeter --help
> Usage: kwhmeter [OPTIONS] SUMINISTRO
> 
> Options:
>   --lista-facturas                Muestra los periodos de facturación
>                                   disponibles  [default: False]
> 
>   --factura TEXT                  Consumos para las facturas especificadas. Se
>                                   puede usar tantas veces como facturas se
>                                   quieran recuperar  [default: False]
> 
>   --fecha-ini [%Y-%m-%d]          Fecha inicio consumos por fecha  
> 
>   --fecha-fin [%Y-%m-%d]          Fecha fin consumos por fecha  
> 
>   --precios                       Añade los precios a cada hora  [default:
>                                   False]
> 
>   --format [screen|cnmc_csv|excel|html]
>                                   Formato de salida  [default: screen]
>   --fichero TEXT                  Fichero de salida (sin extensión)  [default:
>                                   consumos]
> 
>   --help                          Show this message and exit.


El formato de salida cnmc_csv produce un CSV adaptado para poderlo usar en el simulador de facturas de la CNMC: https://comparador.cnmc.gob.es/facturaluz/inicio/


Tambien se puede invocar desde un script de python. Ver el directorio jupyter con ejemplos de uso.